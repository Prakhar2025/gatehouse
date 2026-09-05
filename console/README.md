# Gatehouse Console

The guardian's command surface: review escalations with court-grade evidence,
decide, audit, administer. Telegram handles moments; this handles depth.

## Stack

Next.js 16 (App Router, Turbopack), React 19, TypeScript strict, Tailwind v4,
Radix primitives, Framer Motion, TanStack Table and Query, Geist Sans and Mono,
lucide icons. Design law: flat surfaces, 4px grid, tabular numbers, verdict
colors as the only saturated hues, zero glassmorphism or gradient decoration.

## Commands

```bash
npm install        # one heavy session; after that, kilobytes
npm run dev        # local development
npm run build      # production build (also the type gate)
npm run lint       # eslint
npm run typecheck  # tsc --noEmit
npm run check:i18n # en/hi locale parity (doc 10 criterion 5)
```

## Data layer

`src/lib/api/client.ts` implements the doc 14 contract. The default
transport is live: API routes read the real Dynamo tables server-side with
the default credential chain, and the verdict path (dashboard, queue, case
detail, review) runs on real cases. Household, audit, and benchmark screens
still render seeded sample data until their tables exist; the mock transport
(`mock-data.ts`, deterministic and seeded from the first real soak messages)
remains for previews and tests. The gateway swap is one `setTransport` call; no screen code changes.
Zod schemas in `schemas.ts` mirror the backend contracts and are the drift tripwire.

## Scope note

Built surfaces: dashboard, decision queue (keyboard-first: j/k, Enter, a, w,
Esc), case detail with the full evidence bundle viewer (findings, graph,
timeline, engagement, cost), circle, settings, audit. Auth, onboarding wizard,
and the standalone graph explorer land with the gateway integration per doc 10;
this increment runs on typed mock data by design.
