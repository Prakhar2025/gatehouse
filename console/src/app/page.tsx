"use client";

import { motion } from "framer-motion";
import Link from "next/link";

/**
 * The front door in the owner's own editorial language: Clash Display
 * headlines at poster scale, warm ink, hairlines, amber as the single
 * accent. Product UI preview in the hero per the Linear pattern.
 */

const fade = (d: number) => ({
  initial: { opacity: 0, y: 18 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.6, delay: d, ease: [0.16, 1, 0.3, 1] as const },
});

function ConsolePreview() {
  return (
    <div className="mx-auto mt-16 max-w-3xl rounded-lg border border-line bg-card text-left">
      <div className="flex items-center gap-1.5 border-b border-line px-4 py-3">
        <span className="h-2 w-2 rounded-full bg-line-strong" />
        <span className="h-2 w-2 rounded-full bg-line-strong" />
        <span className="ml-3 font-mono text-[10px] tracking-[0.3em] text-fg-subtle uppercase">
          gatehouse / decision queue
        </span>
      </div>
      <div className="space-y-2 p-4">
        <div className="flex items-center gap-3 rounded border border-scam-line bg-scam-bg px-3 py-3">
          <span className="rounded border border-scam-line px-1.5 py-px font-mono text-[10px] uppercase text-scam-fg">
            scam
          </span>
          <span className="min-w-0 flex-1 truncate text-xs text-fg/85">
            Kotak claimed but link sits on spoof domain kotak.bank.in
          </span>
          <span className="font-mono text-[10px] text-fg-subtle">papa</span>
        </div>
        <div className="flex items-center gap-3 rounded border border-wary-line bg-wary-bg px-3 py-3">
          <span className="rounded border border-wary-line px-1.5 py-px font-mono text-[10px] uppercase text-wary-fg">
            suspicious
          </span>
          <span className="min-w-0 flex-1 truncate text-xs text-fg/85">
            Loan-bait with unverifiable URL shortener; gated, not guessed
          </span>
          <span className="font-mono text-[10px] text-fg-subtle">bhai</span>
        </div>
        <div className="flex items-center gap-3 rounded border border-safe-line bg-safe-bg px-3 py-3">
          <span className="rounded border border-safe-line px-1.5 py-px font-mono text-[10px] uppercase text-safe-fg">
            safe
          </span>
          <span className="min-w-0 flex-1 truncate text-xs text-fg/70">
            Official courier link verified; COD note has no collectable handle
          </span>
          <span className="font-mono text-[10px] text-fg-subtle">papa</span>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <main className="bg-bg text-fg">
      <section className="mx-auto max-w-6xl px-6 pb-24 pt-16 sm:pt-24">
        <motion.div {...fade(0)} className="flex items-center justify-between">
          <span className="font-mono text-[10px] tracking-[0.3em] text-fg-muted uppercase">
            gatehouse
          </span>
          <span className="flex items-center gap-2 font-mono text-[10px] tracking-[0.2em] text-fg-muted uppercase">
            <span className="h-1.5 w-1.5 rounded-full bg-safe-fg" aria-hidden />
            live on aws
          </span>
        </motion.div>

        <motion.h1
          {...fade(0.1)}
          className="font-display mt-14 text-[13vw] font-semibold leading-[0.95] tracking-tight sm:text-[7vw]"
        >
          Nothing <span className="text-accent">harmful</span>
          <br />
          gets past
          <br />
          the gate.
        </motion.h1>

        <motion.p {...fade(0.25)} className="mt-8 max-w-xl text-base leading-7 text-fg-muted sm:text-lg">
          Forward the message. Agents verify the claims, check the registries,
          walk the threat graph. Only a real decision reaches a human, with
          evidence that stands up in court.
        </motion.p>

        <motion.div {...fade(0.35)} className="mt-9 flex flex-wrap items-center gap-4">
          <Link
            href="/console"
            className="rounded bg-bone px-6 py-3 text-sm font-medium text-ink transition hover:bg-white"
          >
            Open the console
          </Link>
          <Link
            href="/how-it-works"
            className="font-mono text-xs tracking-[0.2em] text-fg-muted uppercase transition hover:text-fg"
          >
            how it works →
          </Link>
        </motion.div>

        <motion.div {...fade(0.45)}>
          <ConsolePreview />
        </motion.div>
      </section>

      <section className="border-t border-line">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <motion.h2 {...fade(0)} className="font-display max-w-2xl text-3xl font-medium leading-tight sm:text-5xl">
            Two messages. One difference you cannot see. <span className="text-accent">The gate can.</span>
          </motion.h2>
          <div className="mt-10 grid gap-px overflow-hidden rounded border border-line bg-line md:grid-cols-2">
            <motion.div {...fade(0.1)} className="bg-card p-7">
              <div className="font-mono text-[10px] tracking-[0.3em] text-wary-fg uppercase">
                escalated, with evidence
              </div>
              <p className="mt-4 text-sm leading-7 text-fg/80">
                &ldquo;Sent Rs.349 from Kotak Bank AC X3047 to
                navircbpmobilerec.cf@axisbank. Not you, kotak.com/KBANKT/Fraud&rdquo;
              </p>
              <p className="mt-4 text-xs leading-6 text-fg-muted">
                The link sits on the bank&apos;s genuine surface. No hard fail.
                Conservative gate, guardian sees the evidence, member holds.
                Correct.
              </p>
            </motion.div>
            <motion.div {...fade(0.2)} className="bg-card p-7">
              <div className="font-mono text-[10px] tracking-[0.3em] text-scam-fg uppercase">
                caught as scam
              </div>
              <p className="mt-4 text-sm leading-7 text-fg/80">
                &ldquo;Sent Rs.7.00 from Kotak Bank A/c X3047. Not done by you?
                Tap kotak<span className="font-semibold text-scam-fg">.bank.in</span>
                /KBANKT/Fraud&rdquo;
              </p>
              <p className="mt-4 text-xs leading-6 text-fg-muted">
                kotak.bank.in is a spoof domain outside the registry. Hard fail.
                SCAM verdict, guardian notified, member warned. Caught.
              </p>
            </motion.div>
          </div>
        </div>
      </section>

      <section className="border-t border-line">
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-y-10 px-6 py-16 sm:grid-cols-4">
          {[
            ["480", "adversarial dev cases"],
            ["1.00", "precision, CI [0.989, 1.0]"],
            ["0.0%", "false-gate after calibration"],
            ["$0.00026", "spend per investigation"],
          ].map(([v, l], i) => (
            <motion.div key={l} {...fade(i * 0.08)}>
              <div className="font-display text-3xl font-medium sm:text-4xl">{v}</div>
              <div className="mt-2 text-xs leading-5 text-fg-muted">{l}</div>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="border-t border-line">
        <div className="mx-auto max-w-6xl px-6 py-24">
          <motion.h2 {...fade(0)} className="font-display max-w-3xl text-3xl font-medium leading-tight sm:text-5xl">
            The doctrine is <span className="text-accent">silence</span>. Most
            weeks, the best thing the system does is nothing at all.
          </motion.h2>
          <motion.p {...fade(0.15)} className="mt-6 max-w-xl text-sm leading-7 text-fg-muted">
            Quiet handling for the harmless. A calm hold-off for the gray band.
            Escalation with a court-grade bundle only for hard evidence. Trust
            is preserved by what the system does not say.
          </motion.p>
          <motion.div {...fade(0.25)} className="mt-9 flex flex-wrap items-center gap-6">
            <Link href="/how-it-works" className="rounded bg-bone px-6 py-3 text-sm font-medium text-ink transition hover:bg-white">
              See the pipeline and the law
            </Link>
            <Link href="/trust" className="font-mono text-xs tracking-[0.2em] text-fg-muted uppercase transition hover:text-fg">
              data and trust →
            </Link>
          </motion.div>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-8">
          <span className="font-mono text-[10px] tracking-[0.3em] text-fg-subtle uppercase">
            gatehouse
          </span>
          <span className="text-xs text-fg-subtle">
            Built in the open for the AWS Agents for Humans hackathon. Every
            number links to a committed artifact.
          </span>
        </div>
      </footer>
    </main>
  );
}
