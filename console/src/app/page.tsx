"use client";

import Link from "next/link";
import {
  Beam,
  Counter,
  GridBackground,
  Marquee,
  Noise,
  Reveal,
  SpotlightCard,
} from "@/components/kit";

/**
 * Front door, 2026 standard: grid + grain, product-UI hero, spotlight bento,
 * counters, marquee of stopped scam classes, scroll narrative. The verdict
 * hues stay the only saturated color.
 */

const BENTO = [
  {
    title: "It reads the message like an analyst",
    body: "Triage on Bedrock Nova scores urgency across Hinglish scam scripts, authority impersonation, UPI collect abuse, and the quiet ones that must never wake a guardian.",
    span: "md:col-span-2",
    glow: "255,180,84",
    stat: null as string | null,
  },
  {
    title: "It checks the claim, not the vibe",
    body: "Issuer registries and a curated trusted-service tier adjudicate every brand claim. kotak.bank.in fails. bluedart.com passes. Evidence, not vibes.",
    span: "",
    glow: "61,220,132",
    stat: "PASS / FAIL, per claim",
  },
  {
    title: "It remembers attackers across families",
    body: "Phone, VPA, and UTR references cross into the graph as keyed HMAC hashes. A mule account seen by one household raises taint for every other household.",
    span: "",
    glow: "126,184,255",
    stat: "HMAC-SHA256, never reversible",
  },
  {
    title: "It knows when to shut up",
    body: "The graduated silence law: most messages are handled with zero sound. Gray bands get a calm hold-off, never an accusation. Only hard evidence escalates with a court-grade bundle.",
    span: "md:col-span-2",
    glow: "255,107,107",
    stat: null,
  },
];

export default function LandingPage() {
  return (
    <main className="relative bg-bg text-fg">
      <Noise />
      <GridBackground />

      <section className="relative mx-auto max-w-6xl px-6 pb-16 pt-20 text-center sm:pt-28">
        <Reveal>
          <span className="inline-flex items-center gap-2 rounded-full border border-line bg-card px-3 py-1 font-mono text-[10px] uppercase tracking-[0.25em] text-fg-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-safe-fg" aria-hidden />
            live on aws · real households on soak
          </span>
        </Reveal>
        <Reveal delay={0.08}>
          <h1 className="font-display mx-auto mt-8 max-w-4xl text-[11vw] font-semibold leading-[0.98] tracking-tight sm:text-[5.5rem]">
            Nothing <span className="text-accent">harmful</span>
            <br />
            gets past.
          </h1>
        </Reveal>
        <Reveal delay={0.16}>
          <p className="mx-auto mt-6 max-w-xl text-base leading-7 text-fg-muted sm:text-lg">
            Forward the message. Agents verify the claims, walk the threat
            graph, and only a real decision reaches a human, with evidence.
          </p>
        </Reveal>
        <Reveal delay={0.24}>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/console"
              className="rounded-lg bg-bone px-6 py-3 text-sm font-semibold text-ink transition hover:-translate-y-0.5 hover:bg-white"
            >
              Open the console
            </Link>
            <Link
              href="/how-it-works"
              className="rounded-lg border border-line-strong px-6 py-3 text-sm text-fg-muted transition hover:-translate-y-0.5 hover:text-fg"
            >
              How it works
            </Link>
          </div>
        </Reveal>

        {/* Product-UI-first hero: the queue, rendered */}
        <Reveal delay={0.3}>
          <div className="relative mx-auto mt-16 max-w-3xl">
            <div className="absolute -inset-x-8 -top-8 h-40 rounded-full bg-accent/10 blur-3xl" aria-hidden />
            <div className="relative rounded-xl border border-line-strong bg-card text-left shadow-[0_40px_120px_-30px_rgba(0,0,0,0.9)]">
              <div className="flex items-center justify-between border-b border-line px-4 py-3">
                <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-fg-subtle">
                  decision queue
                </span>
                <span className="font-mono text-[10px] text-safe-fg">● live</span>
              </div>
              <div className="space-y-2 p-4">
                {[
                  ["scam", "text-scam-fg border-scam-line bg-scam-bg", "Kotak claimed but link sits on spoof domain kotak.bank.in", "papa"],
                  ["suspicious", "text-wary-fg border-wary-line bg-wary-bg", "Loan-bait with unverifiable URL shortener; gated, not guessed", "bhai"],
                  ["safe", "text-safe-fg border-safe-line bg-safe-bg", "Official courier link verified; COD note has no collectable handle", "papa"],
                ].map(([v, cls, t, who]) => (
                  <div key={v} className={`flex items-center gap-3 rounded-lg border px-3 py-3 ${cls}`}>
                    <span className="rounded border px-1.5 py-px font-mono text-[10px] uppercase">{v}</span>
                    <span className="min-w-0 flex-1 truncate text-xs text-fg/85">{t}</span>
                    <span className="font-mono text-[10px] text-fg-subtle">{who}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Reveal>

        <div className="mt-14">
          <Marquee
            items={[
              "fake kyc",
              "digital arrest",
              "upi collect abuse",
              "lottery advance-fee",
              "courier customs",
              "otp harvesting",
              "relative impersonation",
              "task scam",
            ]}
          />
        </div>
      </section>

      <Beam />

      {/* Bento */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <Reveal>
          <h2 className="font-display max-w-2xl text-3xl font-medium leading-tight sm:text-5xl">
            An investigation desk, <span className="text-accent">not a chatbot.</span>
          </h2>
        </Reveal>
        <div className="mt-10 grid gap-3 md:grid-cols-3">
          {BENTO.map((b, i) => (
            <Reveal key={b.title} delay={i * 0.08} className={b.span}>
              <SpotlightCard glow={b.glow} className="h-full p-6">
                {b.stat ? (
                  <div className="mb-4 font-mono text-[10px] uppercase tracking-[0.25em] text-fg-subtle">
                    {b.stat}
                  </div>
                ) : null}
                <div className="font-display text-lg font-medium">{b.title}</div>
                <p className="mt-2.5 text-sm leading-6 text-fg-muted">{b.body}</p>
              </SpotlightCard>
            </Reveal>
          ))}
        </div>
      </section>

      <Beam delay={0.2} />

      {/* Proof: the two messages */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <Reveal>
          <h2 className="font-display max-w-3xl text-3xl font-medium leading-tight sm:text-5xl">
            Two messages. One difference you cannot see. <span className="text-accent">The gate can.</span>
          </h2>
        </Reveal>
        <div className="mt-10 grid gap-3 md:grid-cols-2">
          <Reveal delay={0.1}>
            <SpotlightCard glow="245,184,84" className="h-full p-7">
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-wary-fg">
                escalated, with evidence
              </div>
              <p className="mt-4 text-sm leading-7 text-fg/80">
                &ldquo;Sent Rs.349 from Kotak Bank AC X3047 to
                navircbpmobilerec.cf@axisbank. Not you, kotak.com/KBANKT/Fraud&rdquo;
              </p>
              <p className="mt-4 text-xs leading-6 text-fg-muted">
                Link on the bank&apos;s genuine surface. No hard fail.
                Conservative gate, guardian sees evidence, member holds. Correct.
              </p>
            </SpotlightCard>
          </Reveal>
          <Reveal delay={0.2}>
            <SpotlightCard glow="255,107,107" className="h-full p-7">
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-scam-fg">
                caught as scam
              </div>
              <p className="mt-4 text-sm leading-7 text-fg/80">
                &ldquo;Sent Rs.7.00 from Kotak Bank A/c X3047. Not done by you?
                Tap kotak<span className="font-semibold text-scam-fg">.bank.in</span>/KBANKT/Fraud&rdquo;
              </p>
              <p className="mt-4 text-xs leading-6 text-fg-muted">
                Spoof domain outside the registry. Hard fail. SCAM verdict,
                guardian notified, member warned. Caught.
              </p>
            </SpotlightCard>
          </Reveal>
        </div>
      </section>

      {/* Counters */}
      <section className="border-t border-line">
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-y-10 px-6 py-16 sm:grid-cols-4">
          {[
            { v: 480, l: "adversarial dev cases", d: 0 },
            { v: 1.0, l: "precision, CI [0.989, 1.0]", d: 2 },
            { v: 0.0, l: "false-gate after calibration", d: 1, suffix: "%" },
            { v: 0.00026, l: "spend per investigation", d: 5, prefix: "$" },
          ].map((m, i) => (
            <Reveal key={m.l} delay={i * 0.06}>
              <div className="font-display text-3xl font-medium sm:text-4xl">
                <Counter to={m.v} decimals={m.d} prefix={m.prefix ?? ""} suffix={m.suffix ?? ""} />
              </div>
              <div className="mt-2 text-xs leading-5 text-fg-muted">{m.l}</div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="relative border-t border-line">
        <GridBackground className="[mask-image:radial-gradient(ellipse_60%_80%_at_50%_100%,black,transparent)]" />
        <div className="relative mx-auto max-w-5xl px-6 py-24 text-center">
          <Reveal>
            <h2 className="font-display mx-auto max-w-3xl text-3xl font-medium leading-tight sm:text-5xl">
              The doctrine is silence. Most weeks the best thing it does is{" "}
              <span className="text-accent">nothing at all.</span>
            </h2>
          </Reveal>
          <Reveal delay={0.12}>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <Link href="/how-it-works" className="rounded-lg bg-bone px-6 py-3 text-sm font-semibold text-ink transition hover:-translate-y-0.5 hover:bg-white">
                See the pipeline and the law
              </Link>
              <Link href="/trust" className="rounded-lg border border-line-strong px-6 py-3 text-sm text-fg-muted transition hover:-translate-y-0.5 hover:text-fg">
                Data and trust
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-8">
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-fg-subtle">gatehouse</span>
          <span className="text-xs text-fg-subtle">
            Built in the open for the AWS Agents for Humans hackathon.
          </span>
        </div>
      </footer>
    </main>
  );
}
