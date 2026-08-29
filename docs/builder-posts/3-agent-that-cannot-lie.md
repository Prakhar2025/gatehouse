# The agent that cannot lie for you: fencing, canaries, and breaker economics

*Builder post 3 of 3, Gatehouse, August 2026*

Gatehouse investigates fraud on behalf of families, which makes it a target
twice over: attackers can aim at the users, and at the agent. A forwarded
scam message is untrusted input that a powerful model will read closely.
This post is the safety architecture, and the economics that keep it honest.

## The fencing layer

Untrusted content never reaches a prompt raw. Text is normalized, escaped,
and wrapped in explicit data markers with an instruction firewall: the
prompt states that anything inside the markers is evidence under analysis,
never instructions. Every case carries a unique canary token, and any
canary appearance anywhere outbound is a critical alarm. CI plants canaries
and proves the scrubber catches them.

The deeper rule is scope: the agent recommends, it never acts. It cannot
move money, cannot message anyone as a human, and cannot close a case on
its own authority. Engagement with suspected scammers is consent-gated,
turn-budgeted, and stops on a budget breaker mid-conversation if it must.

## Degradation is a feature, not an error path

Every dependency failure has a named, disclosed degraded behavior. Lost
verification forces needs-human, never a quiet safe. A graph outage raises
GRAPH_UNAVAILABLE on the case instead of pretending correlation happened.
Breaker refusals surface as reasons on the bundle. A chaos suite runs the
whole failure matrix on every push, because the doc that promises degraded
behavior and the code that implements it will drift unless a test pins
them together.

One subtlety we got wrong first: an empty result is not an outage. A
message with no phone, VPA, or link produced a graph finding that looked
like a dependency failure, which polluted every degraded-mode statistic.
Findings need both polarities: outage and empty are different answers.

## Breaker economics

Agents that call paid APIs need budgets in code, not in hope. Every call is
metered with token-level cost estimates, breakers refuse at run and USD
caps, and refusal is a visible mode, never silence. Two details we learned
the hard way: price the models by their actual regional inference-profile
ids (ours fell back to a conservative 15x estimate and distorted nothing
only because the error was in the safe direction), and assert the printer
contract, the keys a dashboard reads, in tests, because a runner that pays
for an evaluation and then crashes formatting its own summary is a bug with
a receipt.

## Why this matters for fraud defense specifically

Attackers adapt weekly; the agent's safety envelope has to be boring,
structural, and testable while the detection content evolves. The fencing
layer, provenance fields, polarity-pinned findings, and breaker economics
are the parts we expect to never change. Everything else, lexicons,
thresholds, even models, is versioned data behind them.

The repository carries the failure ledger behind every rule in this post.
Safety claims with receipts, or no claims.
