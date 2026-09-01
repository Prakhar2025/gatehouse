"""Investigator agent: Strands tool-driven evidence gathering (doc 04 section 4).

The doctrine (models propose, code decides) applied one level up. The agent
decides WHICH checks are worth running on a signal; it never produces a
finding itself. Every tool calls the same deterministic verifier the pipeline
has always used and appends the result to a collector the model cannot reach,
so a model that hallucinates a clean bill of health cannot manufacture one:
findings exist only where a real check actually ran.

Two properties follow from the tool signatures, and both are deliberate:

1. No tool accepts message content. Each is closed over the signal under
   investigation, so the model selects a check by name and has no channel to
   launder untrusted text back into the evidence layer (doc 08).
2. No tool returns a verdict. Tools return evidence lines; the guardian
   composes the verdict from findings exactly as it does on the deterministic
   path, so enabling the investigator cannot move a verdict by itself.

Degradation (charter principle 5): any failure inside the agent loop falls
back to the full deterministic sweep and discloses INVESTIGATOR_FALLBACK. The
gate never loses evidence because a model leg failed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gatehouse.agents.schemas import GraphFinding, VerificationFinding
from gatehouse.agents.verify import verify_signal
from gatehouse.packs.schemas import CountryPack

# Tool names are part of the contract: tests assert on them and traces record
# them, so they graduate into constants rather than living in decorators.
TOOL_LINK_REPUTATION = "check_link_reputation"
TOOL_BRAND_CLAIM = "adjudicate_brand_claim"
TOOL_PAYMENT_HANDLES = "check_payment_handles"
TOOL_PRIOR_EVENTS = "correlate_prior_events"

MAX_TOOL_ITERATIONS = 6

_SYSTEM_PROMPT = (
    "You are a fraud investigator gathering evidence about one message. "
    "You have tools that run real registry and threat-graph checks.\n\n"
    "Call the tools that could produce evidence for this message, then stop "
    "and summarise what the evidence shows in one short sentence.\n\n"
    "You do not decide the verdict. Do not guess about anything a tool could "
    "answer. If a tool reports nothing, say so plainly rather than inferring."
)


@dataclass
class InvestigationResult:
    """Evidence gathered for one signal, plus how it was gathered."""

    findings: tuple[VerificationFinding, ...] = ()
    tools_called: tuple[str, ...] = ()
    narrative: str = ""
    degraded_flags: tuple[str, ...] = ()


@dataclass
class Collector:
    """Side channel the tools write findings into. The model cannot read it."""

    findings: list[VerificationFinding] = field(default_factory=list)
    called: list[str] = field(default_factory=list)

    def record(self, name: str, found: list[VerificationFinding]) -> None:
        self.called.append(name)
        self.findings.extend(found)


def _dedupe(findings: list[VerificationFinding]) -> tuple[VerificationFinding, ...]:
    """Same check run twice is one finding; the agent may repeat a tool call."""
    seen: set[tuple[str, str, str]] = set()
    unique: list[VerificationFinding] = []
    for finding in findings:
        key = (finding.subject, finding.check_type, finding.evidence_ref)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return tuple(unique)


def build_tools(text: str, pack: CountryPack, graph: GraphFinding, sink: Collector) -> list[Any]:
    """Build the investigator toolset bound to one signal.

    The signal text is captured here, never passed as a tool argument, which
    is what keeps untrusted content out of the model's writable surface.
    """
    from strands import tool  # local import keeps module import cheap

    @tool(name=TOOL_LINK_REPUTATION)
    def check_link_reputation() -> str:
        """Check every link in the message against the issuer and curated
        trusted domain registries. Reports one line per link, stating whether
        it resolves inside an official domain or is unrecognised. Returns a
        note when the message carries no links at all."""
        found = [f for f in verify_signal(text, pack).findings if f.check_type == "domain_intel"]
        sink.record(TOOL_LINK_REPUTATION, found)
        if not found:
            return "no links present in this message"
        return "\n".join(f"{f.subject}: {f.result} ({f.evidence_ref})" for f in found)

    @tool(name=TOOL_BRAND_CLAIM)
    def adjudicate_brand_claim() -> str:
        """Check whether the message names a known bank, service, or government
        body, and if so whether its links resolve inside that entity's official
        domains. This is the check that separates genuine brand traffic from
        brand spoofing. Returns a note when no known brand is claimed."""
        found = [f for f in verify_signal(text, pack).findings if f.check_type == "issuer_rule"]
        sink.record(TOOL_BRAND_CLAIM, found)
        if not found:
            return "message claims no registry brand, or carries no link to adjudicate"
        return "\n".join(f"{f.subject}: {f.result} ({f.evidence_ref})" for f in found)

    @tool(name=TOOL_PAYMENT_HANDLES)
    def check_payment_handles() -> str:
        """Check any payment handle in the message against the UPI rail
        grammar. A malformed handle is a strong scam indicator. Returns a note
        when the message carries no payment handle."""
        found = [f for f in verify_signal(text, pack).findings if f.check_type == "rail_format"]
        sink.record(TOOL_PAYMENT_HANDLES, found)
        if not found:
            return "no malformed payment handle found"
        return "\n".join(f"{f.subject}: {f.result} ({f.evidence_ref})" for f in found)

    @tool(name=TOOL_PRIOR_EVENTS)
    def correlate_prior_events() -> str:
        """Look up the identifiers in this message against the threat graph to
        see whether they have appeared in prior cases across households, and
        how tainted they are. Returns a note when nothing correlates."""
        sink.record(TOOL_PRIOR_EVENTS, [])
        if graph.unavailable:
            return "threat graph unavailable for this case"
        if not graph.identifiers:
            return "no correlatable identifier in this message"
        return (
            f"{graph.prior_events} prior events across "
            f"{len(graph.identifiers)} identifiers, max taint {graph.max_taint}"
        )

    return [
        check_link_reputation,
        adjudicate_brand_claim,
        check_payment_handles,
        correlate_prior_events,
    ]


async def run_investigation(
    text: str,
    pack: CountryPack,
    graph: GraphFinding,
    model: Any,
) -> InvestigationResult:
    """Gather evidence for one signal through the Strands agent loop.

    Falls back to the deterministic sweep on any failure, disclosing
    INVESTIGATOR_FALLBACK so a degraded investigation is never invisible.
    """
    sink = Collector()
    try:
        from strands import Agent  # local import keeps module import cheap

        agent = Agent(
            model=model,
            tools=build_tools(text, pack, graph, sink),
            system_prompt=_SYSTEM_PROMPT,
        )
        result = await agent.invoke_async(
            "Investigate the message under review and report what the evidence shows."
        )
        narrative = str(getattr(result, "message", "") or "")[:400]
    except Exception as exc:
        # Any model or loop failure degrades to the deterministic sweep.
        return InvestigationResult(
            findings=_dedupe(list(verify_signal(text, pack).findings)),
            tools_called=tuple(sink.called),
            narrative="",
            degraded_flags=(f"INVESTIGATOR_FALLBACK:{type(exc).__name__}",),
        )

    if not sink.called:
        # A loop that called nothing gathered nothing. Sweeping deterministically
        # is the only honest recovery: an empty evidence set would read
        # downstream as "checked and found clean".
        return InvestigationResult(
            findings=_dedupe(list(verify_signal(text, pack).findings)),
            tools_called=(),
            narrative=narrative,
            degraded_flags=("INVESTIGATOR_NO_TOOL_CALLS",),
        )

    return InvestigationResult(
        findings=_dedupe(sink.findings),
        tools_called=tuple(sink.called),
        narrative=narrative,
    )
