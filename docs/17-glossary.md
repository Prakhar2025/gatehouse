# 17 Glossary

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft with 34 terms |

Domain and system terms used across docs 01-16. Definitions are normative:
where code and this glossary disagree, one of them is wrong and that is a bug.

## Fraud Domain

| Term | Definition |
|---|---|
| Digital arrest | Scam where fraudsters impersonate police/CBI/ED via video call, claim the victim is implicated in a crime, and coerce payments or isolation under fake legal authority |
| KYC expiry scam | Phishing claiming Know-Your-Customer documents expired at a bank/wallet/eSIM provider, pressuring urgent re-verification via attacker-controlled links |
| Mule account | Bank/UPI account (often rented or duped from its owner) used to receive and forward fraud proceeds, breaking transaction trails |
| Pig butchering | Long-con investment scam building trust over weeks before extracting large sums into fake trading platforms |
| UPI collect request | Payment rail feature allowing a payer demand; abused by scammers as reverse-pickup ("scan to RECEIVE") confusion attacks |
| VPA | Virtual Payment Address, the handle@bank identifier on India's UPI rail |
| Kit family | A phishing-toolkit lineage: shared code/templates produce sites with common fingerprints detectable across campaigns |

## System Concepts

| Term | Definition |
|---|---|
| Signal | Any inbound artifact submitted for screening: text, screenshot, URL, payment request, contact card |
| Case | One investigation lifecycle over one signal, with state machine defined in doc 03 section 5 |
| Verdict | Terminal classification of a case: SAFE, SUSPICIOUS, SCAM, NEEDS_HUMAN |
| Evidence bundle | Immutable, hash-chained record containing everything that produced a verdict (doc 06 section 2) |
| Gate event | Escalation to the guardian requiring a human decision |
| False gate | Legitimate signal escalated as threatening; the trust-killing failure class, capped at <=5 percent |
| Quiet week | Ideal operating state: high volume screened, zero guardian interruptions, digest proves the value |
| Country pack | Versioned locale artifact set: rails, issuer registries, lexicons, action catalogs, scoring constants |
| Fencing layer | Pipeline normalizing, escaping, wrapping untrusted content before any model sees it (doc 08 section 4) |
| Canary | Unique token embedded per case; appearance anywhere outbound = CRITICAL injection alarm |
| Taint | Graph score of accumulated fraud association propagating through identity links, formula in doc 06 section 3 |
| Sealed vault | Per-household KMS-encrypted storage for raw identifiers extracted during redaction |
| Working copy | Redacted view ([PHONE_1] placeholders) that all downstream processing sees instead of raw content |
| Spend breaker | Circuit breaker tripping agents to NEEDS_HUMAN passthrough when budget caps are exceeded |
| Degraded mode | Explicit reduced-capability operation per the failure matrix (doc 03 section 10); always disclosed, never silent |
| Shadow replay | Re-running past real cases against candidate prompts/packs before promotion, diffing verdicts |
| Soak | Real-household pilot period generating longitudinal honesty reports |
| Override ledger | Record of guardian decisions contradicting verdicts; feeds threshold calibration honestly |

## Technology

| Term | Definition |
|---|---|
| Strands Agents SDK | AWS open-source Python SDK for model-driven agents with tools, hooks, multi-agent patterns; the required framework for this build |
| AgentCore Runtime | AWS managed serverless runtime for agent workloads with session isolation and OTEL observability |
| AgentCore Memory | Managed short/long-term memory service for agents, scoped per household here |
| Agent-as-Tool | Strands pattern composing agents as callable tools inside other agents/orchestrators |
| OpenTelemetry (OTEL) | Vendor-neutral tracing standard; every agent/tool/model call emits spans consumed by CloudWatch |
| Single-table design | DynamoDB modeling multiple entity types in one table with key overloading (layout in doc 06 section 1) |
| HMAC | Keyed hash (SHA256 + KMS-held salt) making identifier storage unlinkable without the key |
| Wilson interval | Confidence interval for proportions used on all published rate metrics |
| PR/FAQ | Amazon working-backwards document: press release + internal FAQs written before the product exists (doc 13) |
| C4 model | Architecture diagramming notation: context (L1), containers (L2), components (L3); levels 1-2 used in doc 03 |
| RFC 7807 | JSON problem-details standard for HTTP error responses (doc 14 conventions) |
| Conventional commits | commit message standard: type(scope): summary, enforced in charter section 6 |
