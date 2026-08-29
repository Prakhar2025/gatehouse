import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Gatehouse Trust Center",
  description: "What Gatehouse stores, what it never stores, and how it behaves when things break",
};

const SECTIONS: { title: string; items: string[] }[] = [
  {
    title: "What we store",
    items: [
      "The evidence bundle that produced each verdict: redacted signal view, verification findings, graph hashes, stage timings, and cost. Hash-chained and immutable.",
      "Keyed HMAC hashes of phone numbers, VPAs, and transaction references for the cross-household threat graph. Raw identifiers never leave the case sandbox.",
      "Guardian decisions and every action as append-only audit entries with chain hashes.",
      "Retention: evidence bundles and audit records 400 days, then gone.",
    ],
  },
  {
    title: "What we never store",
    items: [
      "Raw forwarded message text beyond the redacted view the bundle needs.",
      "Reversible identifiers anywhere in the graph: hashes are keyed, never reversible without the KMS-held salt.",
      "Personal data in logs: every log line passes a scrubber, and CI plants canary strings to prove it.",
      "Any payment credential, ever. The system recommends; it never moves money and never sends messages as a human.",
    ],
  },
  {
    title: "How it behaves when things break",
    items: [
      "Every dependency failure produces a named degraded mode that is disclosed on the case, never a silent pass.",
      "Lost verification forces needs-human rather than a quiet safe verdict.",
      "A hardcoded canary appearing anywhere outbound is a critical injection alarm.",
      "Spend is metered per call with hard breaker caps: overrun becomes an explicit reduced mode, not a surprise bill.",
    ],
  },
  {
    title: "How we measure ourselves",
    items: [
      "Precision, recall, and false-gate rate published with Wilson confidence intervals on a fixed dev split.",
      "A sealed 120-case hold-out opens exactly once before release; its numbers go in the README beside limitations.",
      "Failure taxonomy written from real misses, including the uncomfortable ones.",
      "Weekly soak reports from real households while the pilot runs.",
    ],
  },
];

export default function TrustPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <Link href="/console" className="inline-flex items-center gap-1.5 text-sm text-fg-muted hover:text-fg">
        <ArrowLeft size={14} aria-hidden /> Console
      </Link>
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Gatehouse Trust Center</h1>
        <p className="mt-2 text-sm text-fg-muted">
          Plain statements about data, behavior under failure, and measurement.
          Every claim here traces to a committed document in the repository.
        </p>
      </header>
      {SECTIONS.map((s) => (
        <section key={s.title} className="rounded border border-line bg-card">
          <h2 className="border-b border-line px-4 py-2.5 text-sm font-medium">{s.title}</h2>
          <ul className="list-disc space-y-1.5 px-6 py-3 text-sm text-fg-muted">
            {s.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ))}
      <footer className="rounded border border-line bg-card-muted px-4 py-3 text-xs text-fg-subtle">
        Reference documents: security and privacy (doc 08), evaluation (doc 07),
        silence architecture (doc 19). Incident contact: the guardian of record
        for your household, or the builder contact on the repository.
      </footer>
    </div>
  );
}
