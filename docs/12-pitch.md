# 12 Pitch, Video, and Launch Pack

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Depends on | all prior docs |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft |

## 1. Strategy

The owner's stated weakness is video production; therefore the video is
engineered like everything else: script first, shots second, recording last,
reading aloud instead of performing. Rules explicitly allow slides, screen
recordings, and voiceover with zero camera appearance. Total runtime target:
4 minutes 30 seconds (under the 5:00 cap with safety margin).

Production stack: OBS Studio screen recordings at 1080p, slide deck exported as
images or full-screen browser tabs, voiceover recorded in one quiet-room session
per section (or high-quality TTS if the owner prefers, permitted by rules),
assembled in CapCut/DaVinci free tier with hard cuts only. No transitions, no
music under narration except optional low bed under the cold open.

## 2. Master Script (read-aloud, ~700 words)

### Beat 1: Cold open (0:00 to 0:25)
[SCREEN: phone mockup receiving the scam message, cursor still]
"One in four people on Earth lost money to a scam last year. Worldwide that is
1.03 trillion dollars. Only four percent of victims ever get their money back."
[BEAT] "This is my father's phone. Yesterday it received this message. His bank,
his language, an urgency he almost believed."

### Beat 2: Problem frame (0:25 to 0:55)
[SLIDE: the layer diagram from doc 01]
"Here is why this keeps working. Telco systems fight scams in the network.
Caller ID apps label the number. Banks alert after the money moves. Nobody
defends the actual moment of attack: one human reading one message, alone.
In every family there is one person who becomes the human firewall. That person
has no tooling. I am that person in my family. So I built the tool."

### Beat 3: Product intro (0:55 to 1:20)
[SLIDE: Gatehouse architecture, animated once]
"Gatehouse is an autonomous fraud defense agent for households. Forward it any
suspicious message. A team of AI agents investigates like a professional analyst:
it verifies claims against real bank registries, checks whether this link or
account was seen attacking other families before, and if needed, talks to the
suspected scammer itself to confirm intent. Then it does something unusual:
it stays quiet unless a real decision needs a human."

### Beat 4: Live demo part 1, the attack (1:20 to 2:30)
[SCREEN: real Telegram, real forward, timer visible]
Demo flow: forward the KYC scam -> show verdict card arriving with evidence pair
-> open bundle in console: claims checked, fresh-domain report, graph hit count
-> show engagement transcript snippet where the agent confirmed the scam script.
Narration follows the investigation live, naming each agent as its panel appears.
"The whole investigation took eleven seconds and cost two cents."

### Beat 5: Live demo part 2, the silence (2:30 to 3:10)
[SCREEN: forwarding three benign messages, nothing pings]
"Now the harder test: messages that look scary but are real. A genuine bank
offer. A delivery update. Gatehouse verifies against issuer records and stays
silent. No alarm fatigue. This week my family forwarded eighteen signals.
I was notified exactly once."
[SCREEN: digest card]

### Beat 6: Measurement honesty (3:10 to 3:45)
[SLIDE: metrics table with CIs]
"I hold myself to engineering honesty. On six hundred adversarial test cases,
held out from development: precision ninety-one percent, recall eighty-eight,
false-gate rate three point eight percent, with confidence intervals published
in the repository. Here is where it still fails, and what I am doing about it."
[SLIDE: failure taxonomy, 4 rows, read two honestly]

### Beat 7: Who and why it matters (3:45 to 4:15)
"Gatehouse is for the four hundred fifty million families who already pay for
caller-ID apps and still lose grandparents to digital-arrest scams. It launches
where the damage is worst, India and Southeast Asia and Brazil, then expands.
The detection core is open source so it can be audited. The network gets
stronger with every family that joins, and no family's private data ever leaves
its gate."

### Beat 8: Close (4:15 to 4:30)
"My father's phone got another message today. Gatehouse handled it before he
finished reading the first line." [SCREEN: silent block card] 
"Nothing harmful gets past the gate. Gatehouse."

## 3. Shot List and Recording Order

| # | Shot | Source | Duration | Notes |
|---|---|---|---|---|
| S1 | Scam message arrives on phone mockup | HTML phone-frame page (repo asset) | 10s | Reuse for cold open |
| S2 | Layer diagram | Slide 2 | 20s | Build-in animation once |
| S3 | Architecture | Slide 3 | 15s | Agent names appear in sync |
| S4 | Live forward to verdict | Real Telegram + console, single take | 60s | Do 5 dry runs first; keep timer visible |
| S5 | Bundle deep dive | Console case detail scroll | 20s | Pre-load case, smooth scroll path rehearsed |
| S6 | Engagement transcript | Console transcript viewer | 10s | Highlight two bubbles max |
| S7 | Benign trio + silence | Telegram again | 30s | Show notification absence honestly (no fake sounds) |
| S8 | Digest card | Telegram | 8s | |
| S9 | Metrics + taxonomy | Slides 4-5 | 35s | Read numbers slowly |
| S10 | Silent block close | Phone mockup | 15s | Same frame as S1 for symmetry |

Recording order optimized: S4/S5/S6/S7 same session (staging environment warm),
slides batched separately, S1/S10 last. Every shot recorded twice minimum.

## 4. Slide Deck Outline (8 slides, dark theme)

1. Title: Gatehouse logo + tagline + one-line definition
2. The unprotected layer diagram (telco/callerID/bank layers vs attack moment)
3. Architecture: five agents + tools + AgentCore deployment badges
4. Metrics table with Wilson intervals + cost per investigation
5. Failure taxonomy excerpt (honesty slide)
6. Global map: launch regions + GASA loss data points
7. Family circle product shot (console + Telegram side by side)
8. Close: tagline + repo QR + try-it link

## 5. Devpost Submission Copy Skeleton

- One-liner: Gatehouse is an autonomous fraud-defense agent households forward
  suspicious messages to; five Strands agents investigate, verify, engage, and
  escalate only real decisions.
- About: problem paragraph (GASA + MHA numbers), what it does, how built
  (Strands multi-agent, AgentCore Runtime, Memory, Bedrock models), what is
  measured, links: repo, live console, trust center, builder post.
- Tracks entered: Everyday Agents.
- Assets checklist mirrors hackathon requirements list verbatim, owned by P7.

### 5.1 Rules Compliance Register (from Official Rules read in full, Aug 24)

| Rule | Requirement | Our action |
|---|---|---|
| New Projects Only | Work must be built during Submission Period (Aug 10 to Sep 14); pre-existing incorporated work must be disclosed | Gatehouse repo created Aug 24 (inside window), all code fresh. Prior art disclosure line REQUIRED in README: design informed by builder's earlier projects (ScamShield, TruthLayer, Sentinel), zero code imported. NEVER copy old repos into Gatehouse |
| Judging math | Stage 1 pass/fail theme+tools gate; Stage 2 five equally weighted criteria scored 1-5; bonus up to 0.6 via builder.aws.com posts (0.2 each, MAX THREE posts); final 1-5.6 | Plan THREE posts, not two, to capture full 0.6. Tie-break favors Technical Implementation: deepen Strands usage (hooks, session management, structured output, Agent-as-Tool) as differentiator |
| Testing access | Project must stay available FREE and unrestricted for Sponsor/Admin/Judges until Judging Period ends (Oct 8) | Live demo + console stay up through October; budget credits accordingly; do not tear down staging after submitting |
| Language | ALL materials English (video included) | en-first console strings confirmed; video narration English |
| Video hosting | YouTube or Vimeo, public | YouTube unlisted-to-public flip at submission |
| Drafts | Draft submissions savable before period ends | Save Devpost DRAFT by Sep 5, submit final by Sep 10 |
| AWS Builder ID | Required field | Create early, store in password manager, never commit |
| Credits | Form due Sep 11 12pm PT, one per entrant, expire Oct 31 | Submitted Aug 24; burn plan targets AgentCore+Bedrock during P4-P7 well before expiry |
| Ownership | Original work, solely owned, OSS licenses respected | MIT chosen; audit any copied snippet from tutorials/StackOverflow; document third-party SDK licenses in NOTICE if used |

## 6. builder.aws.com Bonus Post Plan

Title format: "Agents for Humans: Building Gatehouse, a fraud-defense agent for
families". Content arc: why my family needed this -> architecture decisions with
diagrams -> what Strands made easy vs what I engineered around (orchestration as
code, fencing layer) -> eval methodology -> what broke (real entries) -> cost
transparency -> invitation to contribute packs. Two posts planned: build-journey
mid-P6, results post at P7. Both published before deadline per bonus rules.

## 7. Launch Assets Beyond the Hackathon

- Landing page (marketing site separate from console): hero = forward-a-message
  interactive demo sandbox using the eval generator, pricing, trust center link.
- Trust center pages generated from docs 08/06 content in plain language.
- GitHub org + repo social preview images, pack contribution guide.
- Waitlist form feeding launch cohort (target 100 households).
- Press kit one-pager with the GASA/MHA statistics and screenshots.

## 8. Video Acceptance Criteria

1. Runtime 4:00 to 4:40; every required pitch element (problem, who, why)
   covered in the first 90 seconds.
2. Demo shows real end-to-end latency with visible timing, no cuts hiding slowness.
3. Every number spoken appears identically in README metrics (cross-checked).
4. Audio intelligible on a phone speaker (test playback on device).
5. Subtitles burned in (accessibility + judges often watch muted).
