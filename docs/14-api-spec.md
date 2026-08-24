# 14 API Specification

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Depends on | 03-architecture, 06-data-and-graph |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft |

## Conventions

Base URL: `https://api.gatehouse.in/v1` (prod), `/staging` prefix in staging.
Auth: `Authorization: Bearer <JWT>` (Cognito-issued). Machine clients use
per-household API keys: `X-Gatehouse-Key`. All bodies JSON, UTF-8, snake_case.
Errors follow RFC 7807 (`application/problem+json`) with machine-readable `code`.
All endpoints idempotent when called with `Idempotency-Key` header.
Rate limits per household: 60 req/min default, 429 responses carry
`Retry-After`. OpenAPI 3.1 document generated from code (FastAPI) and published
at `/v1/openapi.json`; this markdown is the contract narrative, the generated
schema is the wire truth.

## Endpoints

### Health

```
GET /v1/health -> 200
{ "status": "ok", "version": "1.x.x", "degraded": [] }
```
Public, unauthenticated, load-balancer safe. `degraded` lists active breaker
flags (matches console banner).

### Signals (machine intake)

```
POST /v1/signals
Headers: X-Gatehouse-Key, Idempotency-Key (optional)
{
  "channel": "api",
  "content_type": "text|image|url",
  "text": "raw forwarded text",            # required for text
  "media_url": "https://...",              # required for image (pre-signed upload flow below)
  "member_ref": "external-member-id",
  "note": "optional submitter comment"
}
-> 202 { "case_id": "c_01J...", "state": "RECEIVED", "duplicate_of": null }
-> 200 { "case_id": "...", "duplicate_of": "c_01H..." }   # dedupe window hit
-> 403 problem+json code=HOUSEHOLD_UNVERIFIED
```

Media intake is two-step: `POST /v1/uploads` returns a pre-signed S3 URL (TTL
300s); client uploads, then references the object key in the signal call.

```
GET /v1/cases/{case_id}
-> 200 { case header, state, verdict?, bundle_url?, degraded_flags[], trace_url }
404 problem+json code=CASE_NOT_FOUND (or cross-household access: identical 404, never 403)
```

```
GET /v1/cases?state=ESCALATED&limit=50&cursor=...   -> paginated queue view
GET /v1/cases/{id}/bundle                            -> canonical EvidenceBundle JSON
GET /v1/cases/{id}/audit                             -> audit chain entries
```

### Decisions

```
POST /v1/cases/{case_id}/decision
{
  "action": "warn_member|allow|block_report|verify_with_issuer|ignore",
  "actor": "guardian",
  "note": "optional",
  "notify_member": true
}
-> 200 { "case_id": "...", "state": "CLOSED_ACTIONED", "graph_commit": "queued" }
-> 409 problem+json code=CASE_ALREADY_CLOSED
```
Decision writes are step-up protected when JWT actor lacks recent MFA (doc 08).

### Households and Members

```
POST /v1/households                      { "name": "Sharma Family" }        -> 201
GET  /v1/household                       -> profile, settings, consent ledger
PATCH /v1/household/settings             thresholds/quiet hours/engagement toggle
POST /v1/household/members               { "display_name": "Papa" }         -> invite payload
POST /v1/household/members/{id}/bindings { "channel": "telegram", "handle_ref": "..." }
DELETE /v1/household/members/{id}        -> 204 (binding revoked, audit entry)
POST /v1/household/export                -> async job, signed download URL
POST /v1/household/delete                -> async cascade purge job (typed confirm header)
```

Deletion returns `{ "job_id": "...", "certificate_issuance_eta_hours": 24 }`.

### Packs (read-only)

```
GET /v1/packs                     -> installed packs, versions, checksums
GET /v1/packs/{region}/{version}  -> manifest summary (rules are repo-side, not served raw)
```

### Ops (internal, break-glass role)

```
GET  /v1/ops/spend?window=24h     -> spend meter rollup per agent
POST /v1/ops/breaker/reset        { "breaker": "engage_budget" }   # audited, MFA required
GET  /v1/ops/degraded             -> live failure-matrix status per doc 03 section 10
```

## Webhooks (outbound)

Households may register one HTTPS sink (paid tier): Gatehouse POSTs escalation
cards with `X-Gatehouse-Signature` (HMAC-SHA256, rotating secret per household,
timestamped anti-replay). Payload schema matches the Telegram card structure
plus `bundle_url`. Delivery: 3 retries exponential, then digest fallback.

## Error Code Registry (initial)

| HTTP | code | Meaning |
|------|------|---------|
| 400 | VALIDATION_FAILED | schema violation, details array in problem body |
| 401 | AUTH_REQUIRED / AUTH_EXPIRED | missing or stale credentials |
| 403 | HOUSEHOLD_UNVERIFIED / STEP_UP_REQUIRED | binding absent / MFA challenge needed |
| 404 | CASE_NOT_FOUND / MEMBER_NOT_FOUND | includes cross-household masking |
| 409 | DUPLICATE_REQUEST / CASE_ALREADY_CLOSED | idempotency conflict / lifecycle violation |
| 422 | CONTENT_REJECTED | fence-layer hard refusal (malware-shaped media etc.) |
| 429 | RATE_LIMITED | Retry-After present |
| 500 | INTERNAL | correlation_id always present, page on-call runbook R2 |
| 503 | DEGRADED_WRITE_SPOOLING | doc 03 matrix row 6 in progress |

## Versioning and Deprecation Policy

Breaking changes ship behind `/v2` with 90-day overlap and `Sunset` headers;
additive fields are non-breaking and documented in changelog; webhook consumers
must ignore unknown fields (tolerant reader rule stated in developer docs).
Contract tests in CI pin this entire registry: any endpoint behavior change
without spec + test update fails the build.
