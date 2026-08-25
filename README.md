# Gatehouse

> Nothing harmful gets past the gate.

Autonomous fraud-defense agent for households. Family members simply forward any
suspicious message, payment request, or unknown contact: a team of AI agents
investigates it like a professional fraud analyst (claim verification against
authoritative registries, privacy-preserving cross-household threat graph,
guarded engagement of suspected scammers) and escalates only genuine decisions to
the family guardian with court-grade evidence bundles.

Built on the Strands Agents SDK, deployed on Amazon Bedrock AgentCore.

**Status: P1 skeleton (design docs complete in `docs/`, offline rule engine +
evaluation harness live, agent integration lands in P2).**

## Why

Scam losses hit an estimated $1.03 trillion worldwide in 2024 and one in four
people lost money to scams. Caller ID apps only label phone numbers; banks alert
after money has moved. Nobody investigates the attack itself while it is just a
message sitting on a family member's phone. Gatehouse is that investigator.

## Quick start

```bash
make setup        # venv + pinned dependencies
make check        # format-check + lint (strict) + type-check + fast tests
make test-cov     # tests with 85% coverage gate
make pack-validate
make eval-mini    # offline 30-case benchmark through the deterministic engine
```

No AWS credentials needed for any P1 target: the whole phase runs offline by
design (charter budget rules). AWS integration begins in P2 behind explicit
opt-in extras.

## Repository layout

```
src/gatehouse/        typed source (config, logging, packs, rules, evaluation)
packs/in/pack.yaml    India country pack v0.1.0 (issuers, UPI rail, en+hi lexicons)
docs/                 20 controlled documents (vision, architecture, security, SLOs...)
tests/                pytest suite mirroring every module
requirements-lock.txt 93 pinned transitive dependencies
```

## Honest engineering notes

- The rule classifier is intentionally deterministic: no model calls, no network,
  byte-reproducible scores. It is the fallback brain when models fail and the
  baseline that learned systems must beat in evaluation.
- Every log record passes a mandatory scrubber; CI seeds canary strings to prove
  personal data never reaches observability sinks.
- Metrics publish Wilson 95% intervals because small-sample honesty matters more
  than big-sample vanity.

## Prior art disclosure (hackathon rules compliance)

This project was created new in August 2026 for the AWS Agents for Humans
hackathon. Its design is informed by the builder's earlier independent projects
(ScamShield, TruthLayer, Sentinel), which taught the patterns reused here as
ideas: multi-agent investigation flows, claim verification pipelines, identity
graph scoring. No source code from those projects is imported or copied;
everything in this repository was written fresh during the submission window.

## License

MIT. See LICENSE.

## Docs

Start at `docs/README.md`. Doctrine: `docs/19-silence-architecture.md`.
