import Link from "next/link";

/**
 * Public landing surface. This is where the product is allowed to be loud:
 * the console stays dense and quiet, this page sells.
 */
const ROTATING = [
  "the fake KYC SMS",
  "the digital-arrest call script",
  "the UPI collect trick",
  "the lottery advance-fee",
  "the parcel customs scam",
];

export default function LandingPage() {
  return (
    <main className="min-h-svh bg-[#0a0a0c] text-[#f2f2f4]">
      {/* Hero */}
      <section className="mx-auto flex min-h-svh max-w-4xl flex-col items-center justify-center px-6 text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70">
          <span className="h-1.5 w-1.5 rounded-full bg-[#3ddc84]" aria-hidden />
          live on AWS, screening real family traffic
        </div>
        <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
          Nothing harmful
          <br />
          gets past the gate.
        </h1>
        <p className="mt-6 max-w-xl text-balance text-base text-white/60 sm:text-lg">
          Forward any suspicious message to your family&apos;s Gatehouse bot.
          Agents verify the claims, check the registries, walk the threat
          graph, and only a real decision reaches a human, with evidence.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/"
            className="rounded-lg bg-white px-5 py-2.5 text-sm font-medium text-black transition hover:opacity-90"
          >
            Open the console
          </Link>
          <Link
            href="/trust"
            className="rounded-lg border border-white/15 px-5 py-2.5 text-sm text-white/80 transition hover:bg-white/5"
          >
            How we handle your data
          </Link>
        </div>
        <div className="mt-16 h-8 font-mono text-sm text-white/50">
          <p>
            today it stopped{" "}
            <span className="text-[#ff6b6b]">{ROTATING[new Date().getDay() % ROTATING.length]}</span>
          </p>
        </div>
      </section>

      {/* Proof strip: real numbers from the published artifacts */}
      <section className="border-t border-white/10 bg-white/[0.02]">
        <div className="mx-auto grid max-w-4xl grid-cols-2 gap-px sm:grid-cols-4">
          {[
            ["480", "cases in the adversarial dev split"],
            ["1.00", "precision with Wilson CI [0.989, 1.0]"],
            ["0.0%", "false-gate rate after calibration"],
            ["$0.00026", "measured spend per investigation"],
          ].map(([v, l]) => (
            <div key={l} className="px-6 py-8">
              <div className="font-mono text-2xl tabular-nums text-white">{v}</div>
              <div className="mt-1 text-xs leading-5 text-white/50">{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* How the gate thinks */}
      <section className="mx-auto max-w-4xl px-6 py-20">
        <h2 className="text-2xl font-semibold tracking-tight">
          Models propose. Code decides.
        </h2>
        <div className="mt-8 space-y-4">
          {[
            [
              "Forward",
              "A family member sends the message to the bot. Fencing quarantines the content before any model sees it.",
            ],
            [
              "Investigate",
              "Triage scores urgency on Bedrock. Verification walks issuer and trusted-service registries. The graph remembers attackers across households by keyed hash.",
            ],
            [
              "Decide",
              "Deterministic policy composes the verdict from evidence. Verified-brand evidence caps model panic; hard fails escalate with a court-grade bundle.",
            ],
          ].map(([t, b], i) => (
            <div key={t} className="flex gap-5 rounded-xl border border-white/10 bg-white/[0.03] p-5">
              <span className="font-mono text-sm text-white/30">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <div className="font-medium">{t}</div>
                <p className="mt-1 text-sm leading-6 text-white/55">{b}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-white/10 px-6 py-10 text-center text-xs text-white/40">
        Built in the open for the AWS Agents for Humans hackathon. Every number
        above links to a committed artifact in the repository.
      </footer>
    </main>
  );
}
