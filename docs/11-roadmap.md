# 11 Roadmap and Build Protocol

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Depends on | all prior docs |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft |

## 0. Operating Model

Phase-gated like the Sentinel build: build -> verify -> push -> report -> wait
for owner go. Phases have exit criteria, not dates. The hackathon deadline
(Sep 14, 2026) is treated as a checkpoint we hit mid-journey with submission-
ready artifacts; the product roadmap continues past it without changing shape.
Working rhythm assumes 24-hour availability of the AI engineering team and owner
review gates at phase ends.

## 1. Phase Definitions

### P0 Design Lock (current)
Scope: docs 01-12 finalized, repo initialized, CLAUDE charter active.
Exit: owner approves each doc explicitly (or approves batch); doc versions bumped
to 1.0.0; git history begins with docs commit.

### P1 Skeleton
Scope: repo scaffold (src layout, pyproject strict, ruff+mypy+pytest wired,
GitHub Actions CI green on empty-but-real checks), Makefile (setup/check/test/
lint/run targets), config module, logging setup, MIT LICENSE, README skeleton,
country-pack schema + India pack v0 (rail grammars, 5 issuer YAMLs, lexicons),
eval harness scaffolding with offline deterministic mini-set (30 cases).
Exit: `make check` green in CI; harness runs mini-set locally with mocked agents;
pack schema validates; bootstrap script stub documented.

### P2 Core Agents
Scope: shared schemas (Pydantic), fencing layer complete with unit tests,
triage_agent + verify_agent + graph_agent implemented per contracts against
Bedrock models, orchestrator sequence with idempotency, LocalStack-free mock mode
(mock model provider + mock intel) so full loop runs offline, spend meter module.
Exit: 480-case dev split runs end-to-end in LOCAL_MOCK; schema validation 100%;
deterministic-check precision reported; nightly GitHub Action replays subset.

### P3 Channels + Investigator Live Path
Scope: Telegram bot end-to-end (webhook Lambda, binding flow, escalation cards,
callbacks, /panic, digests), WhatsApp webhook skeleton behind feature flag,
email intake, EventBridge wiring, case store + evidence bundles persisted,
notification service with quiet hours, engage_agent behind household flag.
Exit: Journey A completes on real Telegram from a real phone in under 30s p95
(measured over 50 sends); channel test matrix (doc 05 section 7) green;
duplicate-forward budget protection proven.

### P4 Deployment
Scope: AgentCore Runtime packaging and deploy (staging), SAM stacks for gateway/
tables/bus, observability pipeline with traces visible per agent step, chaos
tests for failure matrix rows 1-7, staging eval replay with tolerance gates,
canary alert drill forced in staging.
Exit: staging URL serves full loop; traces reconstructable per case; chaos suite
green; nightly evals green two consecutive nights; rollback rehearsed once.

### P5 Console
Scope: Next.js app per doc 10 (auth, dashboard, queue keyboard flow, case detail
with bundle viewer, circle, settings, audit), OpenAPI-typed client, locale files
en/hi, performance budgets enforced in CI Lighthouse step.
Exit: acceptance criteria doc 10 section 8 all pass; console drives real staging
cases end-to-end including decisions feeding back into graph commits.

### P6 Evals + Soak + Honesty
Scope: full 600-case set generation final, first sealed hold-out opening (sanity
run), threshold calibration on dev split with published pre/post, soak households
onboarded (builder family + 2 more), weekly soak report automation, failure
taxonomy draft from real misses, cost meter report.
Exit: metrics table populated with Wilson CIs; false-gate rate <= 5% on dev;
soak running clean 7+ days; taxonomy document exists from real cases.

### P7 Release + Submission
Scope: second hold-out opening (final numbers), README final with results +
limitations + architecture diagram, trust center pages live, video produced per
doc 12 script, builder.aws.com bonus post published, Devpost submission filed
early, launch announcement assets.
Exit: submission receipt + all bonus artifacts live; release tag cut; status page
live; launch checklist (docs 09 section 7) fully signed.

### P8 Post-launch (product continues)
Scope: WhatsApp channel GA pending Meta review, Chrome extension, second country
pack (Brazil Pix or Philippines GCash by community pull), pricing experiment,
threat-intel API design partner conversations (the B2B wedge), SOC 2 groundwork.
Exit criteria defined when P7 closes; this phase exists to make the point that
the roadmap does not end at submission.

## 2. Verification Standards per Phase

`make check` = ruff format check + ruff lint + mypy strict + pytest fast suite.
Phase-specific additions listed in exit criteria. Coverage floor: 85% overall,
95% on fencing/orchestrator/spend modules (security-critical paths). Nightly CI =
full offline eval + chaos spot checks. No phase exits with known-red nightly.

## 3. Reporting Protocol

Per phase completion the team reports: what was built, verification output
(pasted, not paraphrased), what broke (appended simultaneously to
docs/what-broke.md), budget spent to date, and the single riskiest thing noticed
during the phase. Owner reviews, then says go.

## 4. Change Control

Docs: version bump + changelog line per edit; contract changes (04 schemas)
require eval impact note before merge. Pack changes require regression gate run.
Prompt changes are code changes: PR + nightly green. Emergency hotfix path
documented in runbooks, retro-documented within 24h.

## 5. Definition of Done (global)

A feature is done when: implemented per contract, type-checked, tested (unit +
integration where applicable), evaluated (if it touches verdict paths), observed
(trace spans present), documented (doc updated + changelog), and demoable from
clean checkout via make targets. Anything less is WIP and does not merge to main.
