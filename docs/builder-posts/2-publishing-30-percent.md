# Publishing 30.6 percent: measurement honesty as a product feature

*Builder post 2 of 3, Gatehouse, August 2026*

A fraud shield that cannot show its misses is a fraud shield you cannot
trust. Gatehouse is a household fraud-defense system: families forward
suspicious messages, agents investigate, and a guardian gets only the
decisions that need a human. Because the product's job is to interrupt
people correctly, we treat measurement as a feature with the same bar as
authentication. This post is the checklist we hold ourselves to, with the
numbers that made each rule necessary.

## Wilson intervals or silence

Every published proportion carries a Wilson 95 percent interval. Precision
1.00 on 336 scam cases is CI [0.9887, 1.0]. That interval is the honesty
between "perfect" and "probably around 99 percent, and we know how
uncertain we are". Small-sample vanity metrics die on contact with this
rule.

## The sealed hold-out opens twice. Twice means twice

The 600-case benchmark is generated with an overlap-proof split: 480 dev,
120 hold-out, and shared template text behind unique reference tokens makes
cross-split leakage structurally impossible. The hold-out opens once as a
mid-build sanity check and once for final release numbers. Every opening
embeds seed, pack version, floor, and reason into the payload. Calibration
happens on the dev split only, and every threshold change publishes its
before and after.

## Failure taxonomy: no invented humility, no hidden failures

Every miss gets classified into seven named buckets: missed pattern family,
language gap, verification tool gap, threshold miscalibration,
orchestration bug, degraded-mode cause, labeling dispute. The counts are
generated from the run's own miss ledger, not written by hand after the
fact. When our first real-model run mislabeled 44 benign messages, the
taxonomy said exactly what they were, and the fix targeted the class.

## The denominator must survive an audit

Our first live soak report read 103 cases from the production table and
implied a 72.7 percent escalation rate. The real household window was 26
cases at 46 percent: the rest were journey-harness fixtures and pre-persistence
test rows. The report now states its exclusions inside the artifact. A
number whose denominator nobody can audit is a number nobody should trust.

## Cost is a metric, not a receipt

The spend meter prices every model call, a breaker caps whole evaluation
runs by USD and call count, and the meter itself is tested: when our rate
table missed the APAC inference-profile prefix, calls were priced at 15x
through the conservative fallback, and the discrepancy between two
measurement surfaces is what exposed it. Fail expensive, never cheap.

## The instrument we are still building

Guardian agreement is the ground truth the system cannot generate alone.
The override ledger ships with the console: real verdicts, real taps, and a
weekly classification of every disagreement into the same seven buckets.
Honest measurement is not a report you write; it is a loop you run.

Repository: every number in this post regenerates byte-identically from a
committed artifact.
