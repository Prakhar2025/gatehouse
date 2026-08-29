"use client";

import { motion } from "framer-motion";
import Link from "next/link";

/**
 * The front door. Product-UI-first hero per the 2026 Linear/Vercel pattern:
 * the real console rendered in miniature, the two-message proof, published
 * numbers. Selling happens here; the product itself stays quiet.
 */

const fade = (d: number) => ({
  initial: { opacity: 0, y: 14 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.5, delay: d },
});

function ConsolePreview() {
  return (
    <div className="mx-auto mt-14 max-w-3xl rounded-xl border border-white/10 bg-[#0e0e11] text-left shadow-[0_30px_80px_-20px_rgba(0,0,0,0.8)]">
      <div className="flex items-center gap-1.5 border-b border-white/5 px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-white/10" />
        <span className="h-2.5 w-2.5 rounded-full bg-white/10" />
        <span className="h-2.5 w-2.5 rounded-full bg-white/10" />
        <span className="ml-3 font-mono text-[10px] text-white/30">
          gatehouse / decision queue
        </span>
      </div>
      <div className="space-y-2 p-4 font-sans">
        <div className="flex items-center gap-3 rounded-lg border border-[#6e1c1c] bg-[#2b0d0d] px-3 py-2.5">
          <span className="rounded border border-[#6e1c1c] px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-[#ff6b6b]">
            Scam
          </span>
          <span className="min-w-0 flex-1 truncate text-xs text-white/80">
            Kotak claimed but link sits on spoof domain kotak.bank.in
          </span>
          <span className="font-mono text-[10px] text-white/40">Papa · 2m</span>
        </div>
        <div className="flex items-center gap-3 rounded-lg border border-[#6b4a0d] bg-[#2a1e06] px-3 py-2.5">
          <span className="rounded border border-[#6b4a0d] px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-[#f5b83d]">
            Suspicious
          </span>
          <span className="min-w-0 flex-1 truncate text-xs text-white/80">
            Loan-bait with unverifiable URL shortener; gated, not guessed
          </span>
          <span className="font-mono text-[10px] text-white/40">Bhai · 14m</span>
        </div>
        <div className="flex items-center gap-3 rounded-lg border border-[#14532d] bg-[#0c2318] px-3 py-2.5">
          <span className="rounded border border-[#14532d] px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-[#3ddc84]">
            Safe
          </span>
          <span className="min-w-0 flex-1 truncate text-xs text-white/60">
            Official courier link verified; COD note has no collectable handle
          </span>
          <span className="font-mono text-[10px] text-white/40">Papa · 1h</span>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <main className="min-h-svh bg-[#0a0a0c] text-[#f2f2f4]">
      <section className="mx-auto max-w-5xl px-6 pb-20 pt-20 text-center sm:pt-28">
        <motion.div {...fade(0)}>
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70">
            <span className="h-1.5 w-1.5 rounded-full bg-[#3ddc84]" aria-hidden />
            live on AWS, screening real family traffic
          </span>
        </motion.div>
        <motion.h1
          {...fade(0.1)}
          className="mx-auto mt-6 max-w-3xl text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl"
        >
          Nothing harmful gets past the gate.
        </motion.h1>
        <motion.p {...fade(0.2)} className="mx-auto mt-6 max-w-2xl text-pretty text-base text-white/60 sm:text-lg">
          Your family forwards the message. Agents verify the claims, check the
          registries, walk the threat graph, and only a real decision reaches a
          human, with evidence that stands up in court.
        </motion.p>
        <motion.div {...fade(0.3)} className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/console"
            className="rounded-lg bg-white px-5 py-2.5 text-sm font-medium text-black transition hover:opacity-90"
          >
            Open the console
          </Link>
          <Link
            href="/how-it-works"
            className="rounded-lg border border-white/15 px-5 py-2.5 text-sm text-white/80 transition hover:bg-white/5"
          >
            How it works
          </Link>
        </motion.div>
        <motion.div {...fade(0.4)}>
          <ConsolePreview />
        </motion.div>
      </section>

      <section className="border-t border-white/10 bg-white/[0.02]">
        <div className="mx-auto max-w-5xl px-6 py-16">
          <motion.h2 {...fade(0)} className="text-2xl font-semibold tracking-tight">
            Two messages. One difference you cannot see. The gate can.
          </motion.h2>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            <motion.div {...fade(0.1)} className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
              <div className="font-mono text-[11px] uppercase tracking-wide text-[#f5b83d]">
                escalated, with evidence
              </div>
              <p className="mt-3 text-sm leading-6 text-white/70">
                &ldquo;Sent Rs.349 from Kotak Bank AC X3047 to
                navircbpmobilerec.cf@axisbank. Not you, kotak.com/KBANKT/Fraud&rdquo;
              </p>
              <p className="mt-3 text-xs leading-5 text-white/45">
                Link sits on the bank&apos;s genuine surface. No hard fail.
                Conservative gate, guardian sees the evidence, member told to
                hold. Correct.
              </p>
            </motion.div>
            <motion.div {...fade(0.2)} className="rounded-xl border border-[#6e1c1c] bg-[#2b0d0d]/60 p-5">
              <div className="font-mono text-[11px] uppercase tracking-wide text-[#ff6b6b]">
                caught as scam
              </div>
              <p className="mt-3 text-sm leading-6 text-white/70">
                &ldquo;Sent Rs.7.00 from Kotak Bank A/c X3047. Not done by you?
                Tap kotak<span className="font-semibold text-[#ff6b6b]">.bank.in</span>
                /KBANKT/Fraud&rdquo;
              </p>
              <p className="mt-3 text-xs leading-5 text-white/45">
                kotak.bank.in is a spoof domain outside the registry. Hard fail.
                SCAM verdict, guardian notified, member warned. Caught.
              </p>
            </motion.div>
          </div>
        </div>
      </section>

      <section className="border-t border-white/10">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-px sm:grid-cols-4">
          {[
            ["480", "cases in the adversarial dev split"],
            ["1.00", "precision, Wilson CI [0.989, 1.0]"],
            ["0.0%", "false-gate rate after calibration"],
            ["$0.00026", "measured spend per investigation"],
          ].map(([v, l], i) => (
            <motion.div key={l} {...fade(i * 0.08)} className="px-6 py-10">
              <div className="font-mono text-2xl tabular-nums">{v}</div>
              <div className="mt-1 text-xs leading-5 text-white/50">{l}</div>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="border-t border-white/10">
        <div className="mx-auto max-w-5xl px-6 py-20 text-center">
          <motion.h2 {...fade(0)} className="text-2xl font-semibold tracking-tight">
            The doctrine is silence.
          </motion.h2>
          <motion.p {...fade(0.1)} className="mx-auto mt-4 max-w-xl text-sm leading-6 text-white/55">
            Most messages are handled without a sound. Gray bands get a calm
            hold-off, never an accusation. Only hard evidence escalates, with a
            bundle that reconstructs the whole investigation. Trust is preserved
            by what the system does not say.
          </motion.p>
          <motion.div {...fade(0.2)} className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link href="/how-it-works" className="rounded-lg bg-white px-5 py-2.5 text-sm font-medium text-black hover:opacity-90">
              See the pipeline and the law
            </Link>
            <Link href="/trust" className="rounded-lg border border-white/15 px-5 py-2.5 text-sm text-white/80 hover:bg-white/5">
              Data and trust
            </Link>
          </motion.div>
        </div>
      </section>

      <footer className="border-t border-white/10 px-6 py-10 text-center text-xs text-white/40">
        Built in the open for the AWS Agents for Humans hackathon. Every number
        links to a committed artifact in the repository.
      </footer>
    </main>
  );
}
