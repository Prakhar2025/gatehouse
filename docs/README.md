# Gatehouse Design Documentation

Document-controlled engineering documentation suite. Every document carries a
version header and changelog; changes without a version bump are defects.

## Reading Order

| # | Document | What it answers |
|---|----------|-----------------|
| 19 | [Silence Architecture](19-silence-architecture.md) | The doctrine: eight layers, graduated silence, lightweight+private constitution, honest limits, golden hour |
| 13 | [PR/FAQ](13-prfaq.md) | Would customers want this? Amazon working-backwards gate |
| 01 | [Vision](01-vision.md) | Problem, market, competition, business model, risks |
| 02 | [Product Spec](02-product-spec.md) | Journeys, features, acceptance criteria |
| 03 | [Architecture](03-architecture.md) | System design, diagrams, model strategy, failure matrix |
| 04 | [Agent Contracts](04-agent-contracts.md) | The five agents as enforceable specifications |
| 05 | [Channels](05-channels.md) | How signals get in, notifications get out |
| 06 | [Data & Graph](06-data-and-graph.md) | Storage layout, evidence bundles, threat graph |
| 07 | [Evaluation](07-evaluation.md) | Datasets, metrics with bars, honesty rules |
| 08 | [Security & Privacy](08-security-privacy.md) | Threat model, fencing layer, launch checklist |
| 09 | [Deployment](09-deployment.md) | Environments, CI/CD, runbooks, cost model |
| 10 | [Console](10-console.md) | Product surface specification |
| 11 | [Roadmap](11-roadmap.md) | Phases P0-P8, eras beyond, money policy |
| 12 | [Pitch](12-pitch.md) | Video script, shot list, submission plan |
| 14 | [API Spec](14-api-spec.md) | REST contract, error registry, webhooks |
| 15 | [Testing Strategy](15-testing-strategy.md) | Test pyramid, gates, release ritual |
| 16 | [Risk Register](16-risk-register.md) | Scored risks with mitigations and early warnings |
| 17 | [Glossary](17-glossary.md) | Normative definitions of every term |
| 18 | [Non-Functional & SLOs](18-nonfunctional-slo.md) | Data classification, SLOs with error budgets, capacity math, concurrency, tenancy, DR |
| -- | [What Broke](what-broke.md) | Real-time failure ledger, appended during build |

## Doctrine Note

Doc 19 (Silence Architecture) is the north star: it overrides older phrasing
wherever they conflict. Notably, charter principle 1 ("recommend, never act")
applies to MONEY and MESSAGE SENDING without exception; passive filtering
(never-ring call screening, network-level link blocking) is governed by doc 19
section 3 graduated silence law instead. Charter amendment pending owner
approval.

## Conventions

- Diagrams: Mermaid (rendered natively on GitHub), C4 levels 1-2 where noted
- Errors: RFC 7807 problem+json (doc 14)
- Metrics: Wilson 95 percent intervals on all proportions (doc 07)
- Commits: conventional commits, no em dashes anywhere (charter section 6)
- Statuses: Draft -> Reviewed -> Locked; only Locked docs gate build phases
