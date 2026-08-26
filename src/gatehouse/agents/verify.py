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
    """Extract candidate hosts. Bare-domain matches that are almost certainly
    NOT hosts (numbers like amounts and timestamps, file fragments) are
    filtered so genuine bank SMS does not drown in phantom domains."""
    hosts: list[str] = []
    for match in _URL_RE.finditer(text):
        host = match.group(1) or match.group(2) or match.group(3)
        host = host.lower().strip("./")
        if not host:
            continue
        labels = host.split(".")
        # A real host has an alphabetic TLD label and at least one
        # alphabetic second-level label; 'rs.83675.45.for' and 'atm.jsp'
        # from amount/time strings do not survive this.
        tld = labels[-1]
        second_level = labels[-2] if len(labels) >= 2 else ""
        if not tld.isalpha() or not any(c.isalpha() for c in second_level):
            continue
        if all(not c.isalpha() for c in labels[0]):
            continue
        # Trailing path fragments captured without a scheme (e.g. 'atm.jsp'
        # after a slash) are not hosts; real registrable hosts carry a
        # known-ish TLD of 2+ letters, which 'jsp' fails as a bare fragment
        # only when it appears alone. Keep it: 'atm.jsp' IS a plausible
        # phishing host. Only drop fragments whose TLD is a number-led or
        # single-letter label.
        if len(tld) < 2:
            continue
        hosts.append(host)
    return hosts


def _domain_matches_issuer(host: str, domains: frozenset[str]) -> str | None:
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

    # 1) URL/domain reputation: trusted, untrusted, or unknown
    for host in _extract_urls(text):
        trusted = _domain_matches_issuer(host, domains)
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
            # not an issuer domain. Fresh-domain intel arrives in P3 (url_intel
            # tool); today the honest verdict is INCONCLUSIVE, not FAIL: we do
            # not yet know age or reputation.
            findings.append(
                VerificationFinding(
                    subject=host,
                    check_type="domain_intel",
                    result="INCONCLUSIVE",
                    evidence_ref="not_in_issuer_registry; age_intel_pends_p3",
                    weight=0.2,
                )
            )

    # 2) Bank-name claims (name or alias) without matching trusted URL
    for issuer in pack.issuers:
        names = [issuer.name, *issuer.aliases]
        if any(n.lower() in text_lower for n in names):
            urls = _extract_urls(text)
            if urls and not any(_domain_matches_issuer(u, domains) for u in urls):
                matched = next(n for n in names if n.lower() in text_lower)
                findings.append(
                    VerificationFinding(
                        subject=matched,
                        check_type="issuer_rule",
                        result="FAIL",
                        evidence_ref=(
                            f"claims {issuer.name} but links point outside "
                            f"{issuer.id} official domains"
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
