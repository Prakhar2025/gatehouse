"""Verify agent: claims and artifact checks (doc 04 section 4).

P2 scope: deterministic checks only (rail grammar, issuer domain/sender
reputation, lexicon crosscheck). The LLM adjudication layer for residual
ambiguity arrives in P2 part 2 behind the same interface, budget-gated.

Every finding cites machine-checkable evidence. Unknown issuers yield
INCONCLUSIVE, never guesses (charter principle 2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gatehouse.agents.schemas import VerificationFinding
from gatehouse.packs.schemas import CountryPack

# Bare-domain form matters: scam SMS almost never carries the scheme, so
# "update KYC at sbi-verify.top" must extract the same host as an https URL.
_URL_RE = re.compile(
    r"https?://([a-zA-Z0-9.-]+)|www\.([a-zA-Z0-9.-]+)|\b([a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class VerifyOutput:
    """All findings from one verify pass."""

    findings: tuple[VerificationFinding, ...]

    @property
    def fails(self) -> tuple[VerificationFinding, ...]:
        return tuple(f for f in self.findings if f.result == "FAIL")


def _extract_urls(text: str) -> list[str]:
    """Extract candidate hosts: scheme'd URLs and www forms first (each
    consumed atomically so their paths are never re-matched), then bare
    domains elsewhere in the text, filtered for phantom tokens that come
    from amounts and timestamps (rs.83675.45.for)."""
    hosts: list[str] = []
    consumed_spans: list[tuple[int, int]] = []
    bare_hits: list[tuple[int, str]] = []
    for match in _URL_RE.finditer(text):
        scheme_host, www_host, bare_host = match.group(1), match.group(2), match.group(3)
        if scheme_host or www_host:
            host = (scheme_host or www_host or "").lower().strip("./")
            if host:
                hosts.append(host)
            # Consume through the end of the scheme'd URL's path: the regex
            # only captures the host, so path tokens after it (ATM.jsp)
            # would otherwise re-match as bare domains.
            path_end = match.end()
            while path_end < len(text) and not text[path_end].isspace():
                path_end += 1
            consumed_spans.append((match.start(), path_end))
        elif bare_host:
            bare_hits.append((match.start(), bare_host.lower().strip("./")))
    for pos, host in bare_hits:
        # Skip bare tokens that merely trail a scheme'd URL's path.
        if any(start <= pos < end for start, end in consumed_spans):
            continue
        labels = host.split(".")
        tld = labels[-1]
        if len(labels) < 2 or len(tld) < 2 or not tld.isalpha():
            continue
        if not any(c.isalpha() for c in labels[-2]):
            continue
        if all(not c.isalpha() for c in labels[0]):
            continue
        hosts.append(host)
    return hosts


def _domain_in_set(host: str, domains: frozenset[str]) -> str | None:
    """Return the trusted domain this host belongs to, if any (suffix match)."""
    for domain in domains:
        if host == domain or host.endswith("." + domain):
            return domain
    return None


def verify_signal(text: str, pack: CountryPack) -> VerifyOutput:
    """Run deterministic verification checks over one signal's text."""
    findings: list[VerificationFinding] = []
    text_lower = text.lower()
    domains = pack.issuer_domains()

    # 1) URL/domain reputation: issuer-official, curated trusted, or unknown.
    # The curated trusted tier (pack.trusted_domains) covers legitimate
    # non-bank link surfaces: e-commerce tracking, logistics, government
    # portals. Without it, every genuine delivery or tax-refund message
    # parked in INCONCLUSIVE forever, because nothing downstream can clear
    # an unverified link.
    for host in _extract_urls(text):
        trusted = _domain_in_set(host, domains)
        if trusted:
            findings.append(
                VerificationFinding(
                    subject=host,
                    check_type="domain_intel",
                    result="PASS",
                    evidence_ref=f"issuer_domain:{trusted}",
                    weight=0.9,
                )
            )
        else:
            curated = _domain_in_set(host, pack.trusted_domain_set())
            if curated:
                findings.append(
                    VerificationFinding(
                        subject=host,
                        check_type="domain_intel",
                        result="PASS",
                        evidence_ref=f"trusted_domain:{curated}",
                        weight=0.85,
                    )
                )
            else:
                # not an issuer or curated domain. Fresh-domain intel arrives
                # in P3 (url_intel tool); today the honest verdict is
                # INCONCLUSIVE, not FAIL: we do not yet know age or reputation.
                findings.append(
                    VerificationFinding(
                        subject=host,
                        check_type="domain_intel",
                        result="INCONCLUSIVE",
                        evidence_ref="not_in_issuer_registry; age_intel_pends_p3",
                        weight=0.2,
                    )
                )

    # 2) Claim adjudication over BOTH registries (issuers first, then curated
    # trusted services). A message naming a known brand splits into two honest
    # outcomes. Links present and all inside that registry's official domains:
    # PASS, claim verified (the false-positive kill switch for genuine bank,
    # delivery, and government traffic). Links present but outside: FAIL, the
    # classic brand-spoof shape. No links: nothing to adjudicate.
    for entity in pack.claim_registries():
        names = [entity.name, *entity.aliases]
        matched = next((n for n in names if n.lower() in text_lower), None)
        if matched is None:
            continue
        urls = _extract_urls(text)
        if not urls:
            continue
        if any(_domain_in_set(u, domains | pack.trusted_domain_set()) for u in urls):
            trusted = next(
                d
                for u in urls
                if (d := _domain_in_set(u, domains | pack.trusted_domain_set())) is not None
            )
            findings.append(
                VerificationFinding(
                    subject=matched,
                    check_type="issuer_rule",
                    result="PASS",
                    evidence_ref=f"claims {entity.name} and links resolve inside {trusted}",
                    weight=0.9,
                )
            )
        else:
            findings.append(
                VerificationFinding(
                    subject=matched,
                    check_type="issuer_rule",
                    result="FAIL",
                    evidence_ref=(
                        f"claims {entity.name} but links point outside {entity.id} official domains"
                    ),
                    weight=0.5,
                )
            )

    # 3) VPA rail grammar: malformed handles are suspicious
    for match in re.finditer(r"\b([a-zA-Z0-9._-]{2,})@([a-zA-Z0-9-]{2,})\b", text):
        handle, bank = match.group(1), match.group(2)
        if not re.fullmatch(r"[a-zA-Z]{2,64}", bank):
            findings.append(
                VerificationFinding(
                    subject=f"{handle}@{bank}",
                    check_type="rail_format",
                    result="FAIL",
                    evidence_ref=f"vpa bank segment '{bank}' violates upi grammar",
                    weight=0.3,
                )
            )

    return VerifyOutput(findings=tuple(findings))
