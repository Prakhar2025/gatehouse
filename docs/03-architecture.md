# 03 System Architecture

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Depends on | 01-vision, 02-product-spec |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft |

## 1. Architecture at a Glance

```
                        HOUSEHOLD LAYER (humans, phones)
   Father forwards WhatsApp msg     Guardian uses console / Telegram
              |                              ^
              v                              | notifications + decisions
   +-------------------+          +---------------------------+
   | INGESTION GATEWAY |          | NOTIFICATION SERVICE      |
   | Telegram bot API  |          | Telegram deep links       |
   | WhatsApp flows    |          | email fallback            |
   | email inbox (IMAP)|          +---------------------------+
   | REST API (API GW) |                        ^
   +---------+---------+                        |
             | signed event                     |
             v                                  |
   +-------------------+   events    +------------------+
   | EVENT BUS         |------------>| CASE STORE       |
   | (EventBridge)     |             | (DynamoDB)       |
   +---------+---------+             +------------------+
             |
             v
   +------------------------------------------------------+
   | AGENTCORE RUNTIME: Gatehouse Investigator            |
   |  Strands multi-agent system (see doc 04)             |
   |  Triage -> Verify || Graph -> Engage? -> Guardian    |
   |  Tools: url_intel, claim_check, graph_query,         |
   |         pack_lookup, engage_channel, notify, redact  |
   +----+------------------+------------------+-----------+
        |                  |                  |
        v                  v                  v
   +----------+    +-------------+    +-------------+
   | AGENTCORE|    | THREAT GRAPH|    | COUNTRY PACK|
   | MEMORY   |    | STORE       |    | REGISTRY    |
   | (household context) | (DynamoDB    |    | (rules,      |
   +----------+    |  hashed IDs)|    |  senders,   |
                   +-------------+    |  scripts)   |
                                      +-------------+
        |                  
        v                  
   +------------------------------------------------------+
   | OBSERVABILITY: OpenTelemetry traces -> CloudWatch,   |
   | spend meter, audit log (immutable, append only)      |
   +------------------------------------------------------+

   CONSOLE: Next.js on Vercel -> API Gateway (signed sessions)
```

## 2. Component Responsibilities

| Component | Responsibility | Technology | Why this |
|---|---|---|---|
| Ingestion gateway | Receive signals from channels, validate, dedupe, PII-minimize, emit signed events | FastAPI on Lambda (via SAM) or AgentCore-side HTTP entry | Team skill: FastAPI. Serverless matches bursty traffic |
| Event bus | Decouple intake from investigation, retries, DLQ | EventBridge + SQS DLQ | Managed, cheap, replayable |
| Investigator | The Strands multi-agent system. One invocation per case | Python Strands Agents SDK on Bedrock AgentCore Runtime | Hackathon-required stack, session isolation, scales to zero |
| Case store | Case lifecycle state, evidence bundles, audit records | DynamoDB single-table | Skill + cost + TTL support for retention |
| Threat graph store | Hashed identifier nodes, edges with taint weights, pattern families | DynamoDB + application-level adjacency lists (abstraction over store) | Neptune is overkill at v1 scale; interface keeps swap-open |
| Country packs | Locale rules: bank sender registries, payment rail formats, scam script library, language config | Versioned JSON/YAML artifacts in S3, loaded by pack_lookup tool | Global core, local packs; auditable and testable without code changes |
| Notification service | Escalation cards, digests, decision callbacks | Telegram Bot API + SES fallback | Telegram first: free, bot-native, inline buttons, global |
| Console | Product surface | Next.js 15 on Vercel, API Gateway backend | Team skill, fast iteration |
| Observability | Traces per agent step, spend meter, alarms | OpenTelemetry to CloudWatch, custom spend meter table | AgentCore emits OTEL natively; matches charter honesty rules |

## 3. Primary Data Flow (Journey A, end to end)

1. Father forwards message to bot. Gateway validates sender is linked to a
   household (channel binding table), computes content hash, dedupes.
2. Redaction pass strips obvious PII into sealed vault fields; investigation sees
   fenced content (doc 08). Signed event emitted to bus.
3. Bus invokes Investigator (AgentCore Runtime) with event reference.
4. Triage classifies. DECISION path continues; NOISE closes silently with digest
   counter increment only.
5. Verify and Graph agents run in parallel via orchestrator. Each returns typed
   structured results. Engage runs conditionally when signals conflict or
   confidence sits in the gray band (0.40 to 0.75).
6. Guardian agent composes verdict + escalation package, writes evidence bundle,
   calls notify tool. Human decision callback updates the case and feeds the
   graph (confirmed scam strengthens taint; false gate records an override event
   that future evals must learn from honestly).
7. Audit record closed. Trace complete. Digest counters updated.

## 4. Model Strategy (Amazon Bedrock only)

Access list confirmed on builder account (per Sentinel build records). No Anthropic
models available on this account; plan assumes none.

| Role | Primary | Fallback | Rationale |
|---|---|---|---|
| Triage (high volume, short text) | Nova Micro | Nova Lite | Millisecond latency class, cents per million tokens, classification-shaped task |
| Claim verification reasoning | Nova Pro | Llama 3.3 70B | Strong structured output, instruction following under fencing |
| Engagement conversation | Nova Lite | Mistral Small variants | Long multi-turn economy, persona adherence adequate |
| Narrative explanation (bundle prose) | Nova Lite | gpt-oss 120b via Bedrock | Cheap fluent summarization of structured findings |
| Embeddings (claim_check) | Titan Embeddings V2 | none needed | TruthLayer lineage, cached in DynamoDB |

Rules: every agent declares its model in config, every call logs token counts to
the spend meter, per-investigation budget enforced in code (default cap defined in
08), circuit breaker flips agents to degraded mode when budget exceeded.

## 5. Deployment Topology

- Environments: dev (local, mock providers), staging (real AWS, synthetic traffic),
  prod (live households). Config via env vars + SSM parameters, never committed.
- Investigator deploys via bedrock-agentcore-starter-toolkit container image to
  AgentCore Runtime. CI builds image, runs tests, deploys staging on merge,
  promotes to prod on tagged release with manual approval.
- Console deploys to Vercel from main branch. API Gateway authorizes via JWT.
- Infrastructure-as-code: SAM template for gateway/store/bus; AgentCore toolkit
  config file versioned in repo. Everything reproducible from clean AWS account
  plus documented bootstrap script.

## 6. Failure Modes Matrix (explicit degradation, no silent passes)

| Dependency fails | System behavior | User-visible effect |
|---|---|---|
| Triage LLM | Rule-based keyword/rail-pattern classifier takes over, marks cases RULE_ONLY | None immediately; digest notes reduced accuracy mode |
| Verify/Graph LLM | Verdict forced to NEEDS_HUMAN with partial evidence | Guardian investigates manually, system says so honestly |
| Graph store | Graph signal omitted, bundle marked GRAPH_UNAVAILABLE | Slightly weaker evidence |
| Engage channel | Engagement skipped, verdict from other signals only | None visible |
| Telegram API | Notifications queued, retry with backoff, SES email fallback after threshold | Delayed cards |
| DynamoDB | Spool to SQS, serve 503 on writes past buffer | Brief intake pause, no data loss |
| Budget breaker trips | All agents drop to NEEDS_HUMAN passthrough | Explicit banner in console: cost protection active |

Every row is asserted by a test in the harness (doc 07) before prod signoff.

## 7. Scale Assumptions (v1 honest numbers)

Design target: 1,000 households, 50 signals per household per month peak, p95
forward-to-verdict under 30 seconds, sustained 5 cases per minute burst capacity.
AgentCore Runtime concurrency and DynamoDB on-demand both absorb this trivially;
the engineering effort goes to correctness and latency inside the investigator,
not infrastructure scale. Post-launch re-evaluation at 10k households triggers the
Neptune-or-not decision on the graph store behind its interface.

## 8. Key Architectural Decisions Record

| ID | Decision | Alternatives considered | Why |
|---|---|---|---|
| ADR-1 | Supervisor-style orchestrator composing four specialist agents via Agent-as-Tool | Free-form Swarm; monolithic single agent | Deterministic escalation paths, per-agent budgets and allowlists, explainable traces. Swarm reserved for future engagement persona rotation |
| ADR-2 | Telegram-first channel, WhatsApp forwarding second | Native SMS app integration first | Store policy and OS restrictions make native SMS fragile; Telegram gives full bot UX day one; WhatsApp flow works within normal forwarding behavior |
| ADR-3 | Hashed identity graph across households | Per-household isolated graphs only | Cross-household reuse detection is the entire intelligence advantage (Sentinel lesson); hashing preserves privacy boundary |
| ADR-4 | Country packs as data, not code | Hardcoded India logic | Global product from line one; packs are testable artifacts contributors can extend |
| ADR-5 | Recommend-never-act enforcement at tool layer | Policy prompts only | Prompt-level safety alone is not a control; dangerous capabilities simply do not exist as tools |
| ADR-6 | Single-table DynamoDB for cases+audit+graph | Relational DB | TTL-based retention, access patterns fit key-value plus adjacency, cost at zero-scale |
