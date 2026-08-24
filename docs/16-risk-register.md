# 16 Risk Register

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Review cadence | end of every phase gate, re-scored |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft with 14 risks scored |

Scoring: Probability (1-5) x Impact (1-5) = Exposure (max 25). Mitigation owner
is named. Risks are re-scored at each phase exit; new risks appended with date.
No risk is deleted, only closed with evidence.

## Active Register

| ID | Risk | P | I | Exp | Mitigation | Early warning signal | Owner |
|----|------|---|---|-----|------------|----------------------|-------|
| R01 | Prompt injection turns agent against member | 3 | 5 | 15 | Fencing layer, canaries, tool allowlists, no-dangerous-tools architecture (doc 08) | Any canary trip or REPORT-as-content anomaly in nightly injection suite | Prakhar |
| R02 | Trust collapse from one publicized bad verdict | 2 | 5 | 10 | Explainable bundles, override ledger, published metrics with limitations, incident comms templates ready before launch | Guardian override rate climbing week over week | Prakhar |
| R03 | False gates destroy quiet-week value prop | 3 | 4 | 12 | Calibration targets with CI regression gates, dev-split-only tuning, false-gate rate as first-class metric (<=5%) | Dev-split false-gate trending up between phases | Prakhar |
| R04 | WhatsApp/Meta policy blocks forwarding flow | 3 | 4 | 12 | Telegram-first parity, email channel, API escape hatch; WhatsApp behind feature flag from day one | Meta policy update notices, delivery failures on webhook | Prakhar |
| R05 | Bedrock model changes/deprecations break agents | 3 | 3 | 9 | Routing table env-configured, fallback chain per job, P4 live verification ritual, pinned IDs in audit | AWS deprecation emails; nightly eval drift on single stratum | Prakhar |
| R06 | Cost blowout from engagement loops | 2 | 4 | 8 | Per-agent budgets, turn caps, breaker cascade, spend alarms (charter section 8) | Spend meter p95 drifting above $0.02/case | Prakhar |
| R07 | Single-builder operational fragility | 4 | 3 | 12 | Async-first alarm design, runbooks before launch, chaos-tested degradation, breaker automation | Any alert requiring instant human response during soak | Prakhar |
| R08 | Eval set leakage/tuning-on-test scandal | 2 | 5 | 10 | Sealed hold-out opened twice max, seeds+versions embedded in metrics.json, pre/post transparency rule (doc 07 section 6) | Any threshold change lacking dev-split justification note | Prakhar |
| R09 | Graph re-identification attack | 2 | 5 | 10 | HMAC+KMS salt, aggregate-only regional views, opt-in intel sharing, boundary dump audit test (doc 08 checklist item 8) | Any raw identifier appearing in graph store dumps | Prakhar |
| R10 | Scam-script drift outpaces pack lexicons | 4 | 3 | 12 | Weekly soak taxonomy review, community pack contribution path, engagement outcomes feed pattern families | Rising INCONCLUSIVE share in engagement results | Prakhar |
| R11 | Hackathon judging deprioritizes solo builders | 3 | 3 | 9 | Submission quality bar independent of team size: deployed system, measured metrics, bonus posts; product continues regardless | n/a (external) | Prakhar |
| R12 | AWS credit exhaustion mid-build | 2 | 3 | 6 | Charter budget caps, credits requested early (form submitted Aug 24), local-first development keeps Bedrock spend minimal | Credit balance below 30 percent before P4 | Prakhar |
| R13 | Console scope creep delays core loop | 3 | 3 | 9 | Doc 10 acceptance criteria frozen; console work confined to P5; queue+detail are the only must-screens | Any P5 ticket without a journey mapping | Prakhar |
| R14 | Legal exposure from engagement transcripts | 2 | 4 | 8 | No-real-data guardrails, ToS language review pre-launch, transcript retention TTL, jurisdiction scoping (launch markets only) | Any engagement session touching regulated advice topics (legal, medical, investment specifics) | Prakhar |

## Closed Risks

(none yet; entries move here with closure evidence at phase gates)
