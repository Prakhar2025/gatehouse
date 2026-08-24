# 05 Channels and Ingestion

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Depends on | 02-product-spec, 03-architecture |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft |

## 1. Channel Strategy Overview

Principle: meet fraud where it arrives, within platform rules, with zero install
friction on protected members' phones. Order below is launch order.

| Channel | Direction | Mechanism | v1 status |
|---|---|---|---|
| Telegram bot | In + out | Bot API, inline buttons, media intake | Primary, full UX |
| WhatsApp forwarding | In only (+ warnings out via guardian's phone) | Member forwards messages to a linked business number; Cloud API webhooks | Secondary, constrained by Meta policy |
| Email inbox | In + out | Dedicated per-household address, IMAP/SES intake | Tertiary: bank emails, phishing mails |
| REST API | In | Signed household API key | Power users + future integrations |
| Chrome extension | In | One-click forward of suspicious page/SMS in Android-emulator flows | Post-v1 |
| Native SMS auto-forward (Android app) | In | Device-resident forwarder app | Post-v1, store-policy review first |

Rationale: native SMS reading is where competitors die (Google Play restrictions on
SMS permission). Forwarding-based ingestion works today on every platform using
behavior humans already have. The product must win with forwarding; deeper
integrations are accelerants, not foundations.

## 2. Telegram Channel Spec

Bot identity: @GatehouseGuardBot (placeholder, final handle checked at registration).

Inbound:
- Text forwards, screenshots, images (OCR path), payment request shares, contact
  cards, voice notes (transcribe then triage).
- Binding: every member links via one-time code from console or guardian invite.
  Unlinked senders receive a polite refusal plus guardian ping option.
- Keyword commands: /panic (force EMERGENCY escalation), /status, /digest,
  /stop (pause screening).

Outbound:
- Escalation cards: verdict headline, why line, evidence pair, buttons
  [Primary action] [Open bundle]. Under 280 chars.
- Decision callbacks: button presses update case, trigger graph commit and audit.
- Digests at configured hour, weekly trust report Sundays.

Rate limits and abuse: per-member intake throttle (30 signals/hour soft, burst to
100), duplicate hash short-circuit returns prior bundle, media size caps (8 MB),
OCR runs only when image lacks usable text layer.

## 3. WhatsApp Channel Spec

Mechanism: member adds the Gatehouse WhatsApp number to contacts named Gatehouse.
Forwarding a message to that number hits the WhatsApp Business Cloud API webhook.

Constraints handled honestly:
- Template message rules limit what we can push proactively; v1 sends verdicts as
  replies inside the 24h customer service window opened by the forward itself,
  which fits the natural flow (member forwarded, reply arrives).
- Guardian escalations on WhatsApp go through the guardian's own Telegram/email;
  cross-channel fan-out is a paid-tier feature post-review.
- Media types supported at launch: text, image, document (payment screenshots).

## 4. Email Channel Spec

Per-household inbound address (hashed alias, e.g. h7k2@gatehouse.in) provisioned at
signup, receiving via SES receipt rule. Intake pipeline identical to chat channels.
Use cases: fake bank KYC emails, investment spam, invoice fraud attempts. Outbound:
digest fallback when Telegram unreachable for over 15 minutes (charter degradation
matrix).

## 5. Ingestion Gateway Pipeline (shared by all channels)

```
receive -> validate sender binding -> normalize (text extraction incl OCR)
   -> content_hash -> dedupe check (TTL 72h)
   -> PII minimization pass (sealed vault writes, redacted working copy)
   -> fencing preparation (doc 08)
   -> signed event -> EventBridge -> case created (CASE_NEW)
```

Gateway is stateless Lambda behind API Gateway (Telegram webhook, WhatsApp
webhook, SES rule target). All secrets via SSM. Webhook signature verification
mandatory (Telegram secret token header, Meta x-hub-signature-256, SES built-in).

Idempotency: event id = channel + content hash + household, dedupe window
configurable per channel (Telegram 72h, email 7d: newsletters repeat).

## 6. Notification Service Spec

Channels: Telegram primary, email fallback, webhook sink (future: user-defined
endpoints, Discord/Slack parity bots post-v1).

Escalation urgency mapping:
- DECISION: single card, standard sound, 1 retry then digest fallback
- EMERGENCY (/panic or detected): card + follow-up ping after 10 min unactioned,
  guardian-only bypass of quiet hours (explicit consent at signup)

Quiet hours: non-emergency escalations queue to morning digest unless guardian
disabled quiet hours. Default ON, 22:00 to 07:00 local.

Copy templates: versioned YAML in repo, en + hi at launch, template tests assert
length limits and required fields (no runtime surprises from a long translation).

## 7. Channel Test Matrix (must-pass before channel ships)

| Scenario | Expected |
|---|---|
| Linked member forwards scam text | Verdict card < 30s p95 |
| Unlinked stranger forwards | Refusal + no case created |
| Same content twice | Second gets DUPLICATE marker, same bundle ref, no double spend |
| Screenshot with no text layer | OCR path completes, verdict produced |
| /panic keyword | EMERGENCY path, quiet-hours bypassed, audit logged |
| Telegram down (chaos test) | Queue + email fallback fires at threshold |
| Button callback after 48h | Graceful expiry message, case still resolvable in console |
