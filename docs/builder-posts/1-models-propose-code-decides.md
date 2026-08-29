# Models propose, code decides: a verdict policy that survived real traffic

*Builder post 1 of 3, Gatehouse, August 2026*

Gatehouse is an autonomous fraud-defense agent for households. Family
members forward suspicious messages to a bot; agents verify claims against
issuer registries, walk a cross-household threat graph keyed by HMAC
hashes, and escalate only genuine decisions to a family guardian with an
immutable evidence bundle. The whole loop runs on Lambda, Bedrock, and
DynamoDB, and the measured cost of one investigation is $0.00026.

This post is about the single engineering decision that mattered most:
where the model's opinion ends and code's decision begins.

## The trap we designed around

The obvious architecture lets the model classify and the code forwards the
answer. That fails in production in a specific, expensive way: the model is
confident in the wrong places. Ours scored a member's own OTP forward at
0.92 scam likelihood, and a genuine courier cash-on-delivery note at 0.86.
Both were benign. Both would have paged a guardian who trusted the system.

We could have tuned prompts forever. Instead we made the policy layer
structural:

- The model returns a likelihood, never a verdict.
- A deterministic rule engine (pack lexicons, rail grammars) bands signals
  independently, and every result carries its provenance: which leg drove
  the final band, and what the rules alone concluded.
- The guardian policy can cap model opinion only when the deterministic
  leg disagrees or is silent. Deterministic evidence is never capped.

## The day real traffic proved it

Three days into live family use, two almost identical "Kotak fraud alert"
messages arrived. One linked to the bank's genuine surface; the claim rule
passed, the VPA handle kept it gated, and the guardian saw a conservative
suspicious with evidence. The other pointed at `kotak.bank.in`, a spoof
domain outside the registry. Hard fail. Scam. Full bundle, member warned.

No prompt change produced that discrimination. The registries did, and the
registry check is pure code. That is the whole argument: put the world's
ground truth in versioned data the code can adjudicate, and let the model
do what it is good at, reading tone and novelty in messy multilingual
text.

## The failure that taught us the most

Our first real-model evaluation run on the 480-case dev split showed
recall 1.0 and a false-gate rate of 30.6 percent. Every miss was benign
traffic the model had panicked on: OTP forwards, linkless bank offers,
delivery notes. The deterministic runner had zero misses on the same
split.

Because every result carried provenance, the diagnosis took minutes, and
the fix was a policy rule, not a prompt: a band driven by the model over
weak rule evidence, on a message with no action channel (no link, no
phone, no VPA, no payment ask), cannot interrupt a human. A gate guards
actions, and there was nothing to act on.

Post-fix: precision 1.0, recall 1.0, false-gate 0.0, with the pre and post
artifacts published byte for byte. The runner, the misses ledger, and the
taxonomy that classified every failure are in the repository.

## What we would tell anyone building this

1. Give every model output a provenance field. It turns "the bot is
   wrong" into a query.
2. Make the deterministic leg load-bearing. It is your fallback under
   outage, your eval baseline, and the counterweight that keeps model
   drift from becoming user harm.
3. Publish your worst numbers first. The 30.6 percent run bought more
   trust with our testers than the perfect one that followed it.

The stack: Strands Agents SDK on Amazon Bedrock (Nova Micro through the
APAC inference profile), structured outputs, and a policy layer that treats
the model as one witness among several.
