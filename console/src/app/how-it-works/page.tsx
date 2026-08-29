import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { PipelineDiagram } from "@/components/pipeline-diagram";

export const metadata = {
  title: "How Gatehouse works",
  description: "The pipeline, the graduated silence law, and the twenty documents behind every claim",
};

const SILENCE = [
  {
    level: "Level 1: Silent handling",
    body: "The overwhelming majority: newsletters, family chatter, genuine delivery updates. Screened, recorded, digested. No member sees anything, no guardian is pinged. The quiet week is the product working.",
  },
  {
    level: "Level 2: Soft warn",
    body: "Gray-band signals get a calm member-visible reply with hold-off guidance while the guardian reviews. Nothing is blocked; nobody is accused.",
  },
  {
    level: "Level 3: The gate",
    body: "Hard evidence or emergency bands escalate to the guardian with the full court-grade bundle: claims, findings, graph taint, cost, chain hash. Humans decide anything touching money.",
  },
];

const LIMITS = [
  "URL shorteners stay unverifiable until URL intel lands: the gate limits instead of guessing.",
  "Benchmark author and lexicon author share a brain; live soak is the independent judge.",
  "Single region, single model leg calibrated; routing changes reopen the calibration protocol.",
  "Guardian agreement is the newest instrument; its first weeks are the real test.",
];

const DOCS: [string, string][] = [
  ["01", "Vision"], ["02", "Product spec"], ["03", "Architecture"], ["04", "Agent contracts"],
  ["05", "Channels"], ["06", "Data and graph"], ["07", "Evaluation"], ["08", "Security and privacy"],
  ["09", "Deployment"], ["10", "Console"], ["11", "Roadmap"], ["12", "Pitch"],
  ["13", "PR/FAQ"], ["14", "API spec"], ["15", "Testing strategy"], ["16", "Risk register"],
  ["17", "Glossary"], ["18", "Non-functional SLOs"], ["19", "Silence architecture"], ["20", "What breaks, and why"],
];

export default function HowItWorksPage() {
  return (
    <main className="min-h-svh bg-[#0a0a0c] text-[#f2f2f4]">
      <div className="mx-auto max-w-4xl space-y-12 px-6 py-12">
        <Link href="/" className="inline-flex items-center gap-1.5 text-sm text-white/50 hover:text-white">
          <ArrowLeft size={14} aria-hidden /> Landing
        </Link>

        <header className="space-y-3">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">How the gate works</h1>
          <p className="max-w-2xl text-base text-white/60">
            One untrusted signal in. Three possible endings. The doctrine that
            decides between them is called the graduated silence law, and it is
            the reason the product can live inside a family chat without
            becoming noise.
          </p>
        </header>

        <section className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
          <PipelineDiagram />
          <p className="mt-3 text-xs text-white/40">
            Models propose scores; deterministic code composes verdicts from
            evidence. Verified-brand proof caps model panic; hard registry
            fails escalate with the full bundle.
          </p>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold tracking-tight">The graduated silence law</h2>
          {SILENCE.map((s, i) => (
            <div key={s.level} className="flex gap-4 rounded-xl border border-white/10 bg-white/[0.03] p-5">
              <span className="font-mono text-sm text-white/30">L{i + 1}</span>
              <div>
                <div className="text-sm font-medium">{s.level}</div>
                <p className="mt-1 text-sm leading-6 text-white/55">{s.body}</p>
              </div>
            </div>
          ))}
          <p className="text-xs text-white/40">
            Full doctrine: docs/19-silence-architecture.md, including the eight
            layers, the engineering constitution, and the honest limits register.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold tracking-tight">What we will not pretend</h2>
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-white/55">
            {LIMITS.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold tracking-tight">Every claim has a document</h2>
          <p className="text-sm text-white/55">
            The repository carries twenty controlled documents. Each is
            versioned, changelogged, and linked below: nobody has to read all
            twenty, but every number and rule on this site lives in one of them.
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {DOCS.map(([n, t]) => (
              <a
                key={n}
                href={`https://github.com/Prakhar2025/gatehouse/blob/main/docs/${n}-${
                  ["vision","product-spec","architecture","agent-contracts","channels","data-and-graph","evaluation","security-privacy","deployment","console","roadmap","pitch","prfaq","api-spec","testing-strategy","risk-register","glossary","nonfunctional-slo","silence-architecture"][Number(n) - 1]}.md`}
                target="_blank"
                rel="noreferrer"
                className="rounded border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/60 transition hover:border-white/25 hover:text-white"
              >
                <span className="font-mono text-white/35">{n}</span> {t}
              </a>
            ))}
          </div>
          <p className="text-xs text-white/40">
            Plus the running failure ledger (what broke and why) and the
            published evaluation artifacts under docs/eval-results/.
          </p>
        </section>

        <div className="flex flex-wrap gap-3 border-t border-white/10 pt-8">
          <Link href="/console" className="rounded-lg bg-white px-5 py-2.5 text-sm font-medium text-black hover:opacity-90">
            Open the console
          </Link>
          <Link href="/" className="rounded-lg border border-white/15 px-5 py-2.5 text-sm text-white/80 hover:bg-white/5">
            Back to the story
          </Link>
        </div>
      </div>
    </main>
  );
}
