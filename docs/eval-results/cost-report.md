# Cost Report (staging evaluation, 2026-08-27)

Measured, not estimated: every number below comes from the SpendMeter
records of actual runs against the real model (apac.amazon.nova-micro-v1:0)
unless marked otherwise.

## Per-run measured spend

| Run | Cases | Model calls | Spend USD | Mean per case |
|---|---|---|---|---|
| Live smoke (2 cases, first deploy) | 2 | 2 | 0.0081 | 0.0040 |
| Staged smoke (8 stratified dev cases) | 8 | 8 | 0.0021 | 0.00026 |
| Staged dev run, pre-calibration | 480 | 471 | 0.1251 | 0.00026 |
| Staged dev run, post-calibration | 480 | 470 | 0.1249 | 0.00026 |
| Total staging evaluation spend to date | | 951 | 0.2602 | |

Bar: 0.02 USD mean per investigation (doc 07 section 3). Measured mean is
0.00026 USD, roughly 76x under the bar. The soft development budget
(charter section 8, 20 USD total Bedrock) stands at about 1.3 percent
consumed by evaluation.

## Corrections worth recording

The first live smoke reported 0.0040 USD per case on the case trace; the
same traffic prices at 0.00026 USD after the meter learned to resolve the
APAC inference-profile prefix (failure taxonomy, live observation 2). The
conservative fallback rate did its job (over-priced, never under-priced),
so no budget decision was made on inflated numbers in the unsafe
direction.

## Projection at v1 scale

Nightly 200-case replays: about 0.05 USD per night, about 1.6 USD per
month. Soak households add per-forward costs at the measured per-case rate;
at 50 forwards per household per week across three households that is
about 0.04 USD per week. Infra (DynamoDB, Lambda, EventBridge) at v1 scale
sits inside free tiers per the money policy (doc 11 section 5).

## What this report does not yet include

Console (P5) has no cost surface yet. WhatsApp channel and engage-agent
live loops are flag-gated and unmeasured until they run; they inherit the
same meter discipline when they do.
