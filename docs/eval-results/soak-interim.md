# Soak Report: interim, soak window only (Aug 27 onward)

Scope discipline: the cases table also carries 93 pre-persistence test
items and 77 journey-harness runs from Aug 26. Those are test artifacts,
excluded here. This report covers only the live soak window through the
real aggregation engine; the final week-one report replaces it around
Sep 3 when the 7-day clock closes.

Per day (includes 5 tagged smoke cases from the two deploy verifications):

| Day | Cases | Escalations |
|---|---|---|
| Aug 27 | 22 | 8 |
| Aug 28 | 4 | 4 |

---
# Soak Week Report

Window: 7 days (1787788800 .. 1788393600, epoch seconds)

| Metric | Value |
|---|---|
| Cases screened | 26 |
| Escalations (SUSPICIOUS+SCAM) | 12 (0.4615) |
| Quiet week | no |
| Degraded-case share | 0.0 |
| Spend total / mean / p95 USD | 0.007058 / 0.000271 / 0.0003 |
| Latency p50/p95 ms | None / None |

Verdict distribution:

| Verdict | Count |
|---|---|
| SAFE | 14 |
| SCAM | 4 |
| SUSPICIOUS | 8 |

Triage distribution:

| Class | Count |
|---|---|
|  | 13 |
| DECISION | 8 |
| NOISE | 2 |
| SCREEN | 3 |

Override ledger: not present yet; guardian agreement unmeasured this week.
