# Failure Taxonomy (dev split, real model)

Appendix required by doc 07 section 5. Every entry below comes from an
actual misclassified case or an actual live observation during the staging
evaluation of 2026-08-27. No invented humility, no hidden failures.

Run identity: full-pipeline-staging-v1, dev split, seed 4207, pack v0.2.0,
floor 0.40, model apac.amazon.nova-micro-v1:0, 480 cases, spend 0.1249 USD.

## Pre-calibration misses (44 false gates, 0 misses on scams)

Source artifact: staging-dev-metrics-pre.json (byte-preserved).

| Taxonomy class | Count | What actually happened |
|---|---|---|
| threshold_miscalibration | 44 | The model leg over-flagged benign traffic; the rule leg alone had zero misses on the same split |

Breakdown of the 44 by stratum and mechanism:

1. otp_forward, 16 of 16 flagged. Nova Micro scores "OTP present" as high
   danger (0.85+ likelihood) regardless of context. In Gatehouse the member
   forwarding their own OTP to the household is the product's normal use;
   the message carries no link, no phone, no VPA, no payment ask.
2. legit_bank_offer, 15 of 24 flagged. Linkless or issuer-linked genuine
   offers; the model reads "bank + offer" as phishing risk.
3. delivery_update, 10 of 20 flagged. Genuine courier notes with official
   tracking links; the word "pay" (cash on delivery) pushed model likelihood
   into the DECISION band, and the payment guard on the issuer-verified
   rescue then kept the escalation alive.
4. newsletter_promo, 3 of 28 flagged. Linkless promotional traffic scored
   SCREEN by the model alone.

## Live observations (real Telegram path, 2026-08-27)

1. A genuine BlueDart tracking forward reached the guardian as SUSPICIOUS
   (case b61b217725a04aa0). Cause: model likelihood 0.85+ (DECISION band)
   while the evidence-based rescue only covered the SCREEN band. Fixed the
   same day: verified-claim evidence now caps a model-panicked DECISION when
   no collectable handle exists.
2. The live spend trace reported roughly 0.0040 USD per case while the
   runner measured 0.00026 USD: the meter's rate table missed the APAC
   inference-profile prefix and priced calls at the conservative fallback
   (about 15x). Meter now resolves regional profile prefixes to the
   underlying model price.

## Resolution and verification

Fix wave (channel-free cap with model-provenance discriminator, verified
COD rescue, band_source and rule_class contract fields) was calibrated on
the dev split only, per doc 07 section 6. Post-calibration run
(staging-dev-metrics.json): precision 1.0 CI(0.9887, 1.0), recall 1.0
CI(0.9887, 1.0), false-gate 0.0, no misses in any taxonomy class.

The sealed hold-out remains unopened; it judges the final numbers at the
release gate.

## Honest limits of this taxonomy

- The benchmark generator and the detection lexicons share an author; the
  real-miss soak households are the independent judge that matters.
- Model-leg calibration is one model deep (Nova Micro). A routing change
  reopens this appendix with a new pre/post pair.
- The channel-free doctrine assumes no action is possible without an
  in-text handle; social-engineering that moves the victim to a known
  number from memory evades it by design (and lands in soak reports if it
  ever recurs).
