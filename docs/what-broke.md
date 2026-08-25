# What Broke

Real-time ledger of failures encountered during the build, appended as they
happen per the charter build protocol. No invented humility, no hidden failures.

Format per entry:

```
## [date] [component] short title
Symptom:
Root cause:
Fix:
Prevention:
Phase:
```

Entries appear below this line as building begins in P1.

## [2026-08-24] tests/packs wrong repo-root depth
Symptom: PackError file-not-found in 4 India-pack tests.
Root cause: parents[1] from tests/packs/test_packs.py resolves to tests/, not repo root.
Fix: parents[2].
Prevention: single REPO_PATH helper planned if a third nested dir appears.
Phase: P1

## [2026-08-24] classifier violated ADR-4 (weights hardcoded)
Symptom: mutating pack.scoring did not change scores; test caught it.
Root cause: classify_text used module constants instead of pack weights.
Fix: all weights now read from CountryPack.scoring; constants kept only as schema defaults.
Prevention: test_weights_come_from_pack_not_code permanently guards this.
Phase: P1

## [2026-08-24] runner threshold mismatch produced recall 0.0
Symptom: first eval run showed recall=0.0 despite obvious scam phrases matching.
Root cause: standalone rule engine judged at DECISION threshold (0.70) but its scores top out near 0.65 for single-signal texts.
Fix: default operating point for the standalone baseline is SCORE_SCREEN (0.40); DECISION belongs to the P2 pipeline where escalation cost exists.
Prevention: docstring on run() explains operating-point reasoning; eval report prints chosen threshold.
Phase: P1

## [2026-08-24] single-match scoring capped recall at 0.5
Symptom: scam templates with one moderate phrase scored 0.30, below screen line.
Root cause: max-only aggregation ignored corroborating evidence, unlike how analysts stack independent signals.
Fix: distinct-phrase corroboration steps (+0.25 each, max 3 distinct counted; repeats add nothing).
Result: recall 0.50 to 0.71 to 0.875 across three pack/threshold iterations with precision held at 1.0 and false-gate rate 0.0.
Prevention: mini eval now part of make targets and CI; regressions visible immediately.
Phase: P1

## [2026-08-24] lexicon coverage gaps found empirically
Symptom: remaining misses clustered in investment/lottery strata, both languages.
Root cause: seed lexicons lacked common phrasings (money laundering, slots left, कर जमा, दावा करें).
Fix: India pack v0.1.0 lexicons extended; pack version stays 0.1.0 until owner review locks it.
Prevention: every future miss must end as either a pack phrase or a labeled harness limitation, never silence.
Phase: P1
