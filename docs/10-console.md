# 10 Console Specification

## Document Control

| Field | Value |
|---|---|
| Version | 0.2.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Depends on | 02-product-spec, 03-architecture |
| Last updated | 2026-08-27 |

## Changelog

| Version | Change |
|---|---|
| 0.2.0 | Core console implemented per section 3 on the locked stack (Next.js 16, React 19, Tailwind 4, Radix, Motion, TanStack, Geist): dashboard with gate hero and published confidence intervals, keyboard-first decision queue, case detail with the full evidence bundle viewer (findings, graph, timeline, engagement, cost), circle, settings, audit; en/hi copy with a CI-ready parity script; typed mock transport mirrors doc 14 so the gateway swap touches no screens. Deferred with reasons: auth and onboarding (gateway integration), standalone graph explorer (bundle-level graph panel ships now), Lighthouse CI budgets (no JS CI yet) |
| 0.1.0 | Initial draft |

## 1. Role and Principles

The console is where the guardian feels command of the gate: review, decide,
audit, administer. Telegram handles moments; console handles depth. Principles:
keyboard-first review flow, receipts over vibes (evidence beside every number),
zero dead ends (every state has an obvious next action), responsive down to
mobile widths because guardians live on phones.

Stack: Next.js 15 App Router, TypeScript strict, Tailwind + shadcn/ui components,
TanStack Query for data, Zod schemas mirrored from backend contracts, Vercel
deploy. Auth: Cognito hosted UI, MFA enforced for guardian role.

## 2. Information Architecture

```
/login                    auth (email+OTP member, password+MFA guardian)
/onboarding               create household, invite members, link channels,
                          self-test wizard (doc 02 journey D)
/dashboard                today: queue summary, quiet-week story, circle status
/queue                    decision queue (the work surface)
/cases/[id]               case detail: evidence bundle viewer
/graph                    threat graph explorer (household-visible slice)
/circle                   family circle management
/settings                 thresholds, quiet hours, language, engagement toggle,
                          data controls (export/delete)
/audit                    immutable audit log browser
/trust                    trust center pages (public route group)
```

## 3. Key Screens

### Dashboard

Hero card answers one question: "Does the gate need me?" States:
- ALL CLEAR: "14 screened this week. 12 handled silently. Nothing needs you."
  with tiny sparkline of verdict mix. This empty state is the product's pride,
  designed with the same care as busy states.
- NEEDS YOU: top escalation card inline with primary action button.
- DEGRADED: honest banner when breaker/degraded mode active (never hidden).

Below: circle status (each member: linked channels, last signal, health),
weekly trend mini-charts, recent silent blocks list (collapsed).

### Decision Queue (/queue)

Ranked list (urgency, then age). Row shows: verdict chip, why-line, member who
forwarded, time, confidence with evidence pair on hover. Keyboard flow:
j/k navigate, o open, a approve recommended action, w warn member, s open bundle,
esc back. Bulk actions limited deliberately (fraud review is not email); batch =
max 5 similar-pattern cases with identical reason codes.

Empty state: quiet-week illustration plus digest recap link.

### Case Detail (/cases/[id])

Sections in order:
1. Signal view (redacted render exactly as investigation saw it, media thumbnails)
2. Verdict block: verdict, confidence bar, reason chips, thresholds used
3. Claims table: claim, check type, result icon, evidence popover
4. URL/domain report cards (age badge, kit-family match, screenshot ref)
5. Graph panel: found identifiers (hashed display), prior events count, taint
   score with formula tooltip, mini topology render (adjacency two-hop, SVG,
   no heavy libs at v1)
6. Engagement transcript (if any): chat bubbles, outcome chip, stop-reason
7. Cost block: tokens and USD per stage (transparency builds trust with the
   exact audience reading this screen)
8. Action bar: recommended action primary, alternatives dropdown, warn-member
   composer with template picker, resolve buttons, all writing audit events

### Graph Explorer (/graph)

Household-visible subgraph plus opt-in regional fog view (aggregate counts only).
Search by identifier prefix (hashed input accepted). Node detail drawer with
event history (case links), families, taint timeline. Honest coverage banner
("network memory: N events across M households").

### Circle (/circle)

Member cards with binding status, per-member settings (engagement consent shown),
invite flows, panic-button explanation card for printing/sharing to elders,
warning-history per member.

### Settings

Threshold sliders (escalation floor, gray band bounds) with plain-language
effects preview, quiet hours with timezone, language switcher, engagement master
toggle, data controls: export (JSON download), delete household (typed
confirmation, certificate preview), consent ledger view.

### Audit (/audit)

Append-only log browser: filter by case/member/actor/event type; entries are
read-only with hash chain indicator per case; export CSV for compliance-minded
guardians.

## 4. Component Library (build order)

Primitives: Button, Chip/VerdictBadge, ConfidenceBar, EvidencePopover,
HashChip (truncated HMAC with copy), TimestampAgo, EmptyState, Banner.
Composite: EscalationCard, ClaimTable, UrlReportCard, GraphMiniPanel,
TranscriptViewer, CostBlock, MemberCard, ThresholdSlider, DigestPreview.
Layout: ConsoleShell (sidebar + topbar with household switcher), QueueRow,
DetailSection.

Design tokens: single theme, light/dark, accessible contrast (WCAG AA), verdict
color semantics consistent everywhere (SAFE=green, SUSPICIOUS=amber, SCAM=red,
NEEDS_HUMAN=blue). Icons: lucide. No marketing-site aesthetics inside the product;
console stays dense and calm.

## 5. State and Data Layer

TanStack Query with typed fetchers generated from OpenAPI spec (gateway exposes
spec). Optimistic updates ONLY for reversible actions (mark-read); verdict
actions always round-trip with confirmation state. WebSocket not needed v1:
polling intervals tuned per route (queue 15s, detail on-focus refresh) keeps
serverless costs trivial and code simple. Error states follow degradation honesty:
API unreachable shows cached data with explicit stale banner, never blank screens.

## 6. Accessibility and i18n

Full keyboard map documented in-app (? shortcut opens cheatsheet). Screen reader
labels on every interactive element; focus management on modal flows. Copy lives
in locale files (en, hi at launch); RTL-ready layout rules adopted now to avoid
rework when Arabic/Urdu packs arrive.

## 7. Performance Budgets

Lighthouse mobile >= 90 on dashboard/queue; JS bundle < 250KB gz initial;
case-detail interactive < 2s p75 on mid-range Android over 4G (guardians share
links to family, phones vary); images lazy with blur placeholders; graph SVG
virtualized beyond 200 nodes (regional fog view caps rendered nodes at 150 with
aggregation).

## 8. Acceptance Criteria

1. Full Journey D (onboarding to self-test) completable on a phone browser.
2. Queue keyboard flow resolves 10 cases without touching mouse.
3. Every evidence bundle element from doc 06 schema renders, including degraded
   flags and cost blocks.
4. Lighthouse budgets met on CI-run audits for the three core routes.
5. Locale file completeness test: en/hi parity enforced in CI.
