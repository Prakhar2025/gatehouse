"use client";

/**
 * Case detail (doc 10 section 3): signal view, verdict block, claims table,
 * URL report cards, graph panel, engagement transcript, cost block, action
 * bar. The bundle renders read-only; every action writes an audit entry.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Tabs from "@radix-ui/react-tabs";
import { ArrowLeft, Check, Minus, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import type { CheckResult, EvidenceBundle, VerificationFinding } from "@/lib/api/schemas";
import { copyFor, useLocale } from "@/lib/i18n";
import {
  Banner,
  Chip,
  ConfidenceBar,
  EmptyState,
  HashChip,
  Skeleton,
  TimeAgo,
  VerdictBadge,
} from "@/components/primitives";

export default function CaseDetailPage() {
  const params = useParams<{ id: string }>();
  const caseId = params.id;
  const { locale } = useLocale();
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);

  const bundle = useQuery({
    queryKey: ["bundle", caseId],
    queryFn: () => api().getBundle(caseId),
  });
  const summary = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => api().getCase(caseId),
  });

  const decide = useMutation({
    mutationFn: (action: "warn_member" | "allow" | "verify_with_issuer") =>
      api().postDecision(caseId, { action }),
    onSuccess: () => {
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["case", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
    onError: (err) => setActionError(err instanceof ApiError ? err.code : "NETWORK_ERROR"),
  });

  if (bundle.isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-3 p-4 md:p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-24" />
        <Skeleton className="h-40" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (bundle.isError || !bundle.data) {
    return (
      <div className="mx-auto max-w-4xl p-4 md:p-6">
        <EmptyState
          title={copyFor(locale, "common_error_title")}
          body={copyFor(locale, "common_error_body")}
          action={
            <button
              type="button"
              className="rounded border border-line px-3 py-1.5 text-sm"
              onClick={() => void bundle.refetch()}
            >
              {copyFor(locale, "common_retry")}
            </button>
          }
        />
      </div>
    );
  }

  const b = bundle.data;
  const closed = summary.data?.state === "CLOSED_ACTIONED";

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between gap-2">
        <Link
          href="/console/queue"
          className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
        >
          <ArrowLeft size={14} aria-hidden /> {copyFor(locale, "nav_queue")}
        </Link>
        <div className="flex items-center gap-2">
          <HashChip value={b.bundle_id} label="bundle id" />
          <span className="font-mono text-[11px] text-fg-subtle">pack v{b.pack_version}</span>
        </div>
      </div>

      {actionError ? (
        <Banner tone="error" title={`${copyFor(locale, "common_error_title")}: ${actionError}`} />
      ) : null}

      {/* 1. signal view, exactly as the investigation saw it */}
      <section aria-labelledby="sig-h" className="rounded border border-line bg-card">
        <h2 id="sig-h" className="border-b border-line px-4 py-2.5 text-xs font-medium text-fg-muted">
          {copyFor(locale, "case_signal")}
        </h2>
        <div className="px-4 py-3">
          <div className="flex items-center gap-2 text-xs text-fg-muted">
            <span className="font-medium text-fg">{b.signal_view.member_name}</span>
            <span>{b.signal_view.channel}</span>
            <TimeAgo iso={b.signal_view.received_at} />
          </div>
          <pre className="mt-2 whitespace-pre-wrap break-words font-sans text-sm leading-relaxed">
            {b.signal_view.text}
          </pre>
        </div>
      </section>

      {/* 2. verdict block */}
      <section aria-labelledby="verdict-h" className="rounded border border-line bg-card">
        <h2 id="verdict-h" className="border-b border-line px-4 py-2.5 text-xs font-medium text-fg-muted">
          {copyFor(locale, "case_verdict")}
        </h2>
        <div className="flex flex-wrap items-center gap-3 px-4 py-3">
          <VerdictBadge verdict={b.verdict} />
          <ConfidenceBar value={b.confidence} />
          {b.degraded_flags.length > 0 ? (
            <Banner tone="degraded" title={b.degraded_flags.join(", ")} />
          ) : null}
        </div>
        <div className="flex flex-wrap gap-1.5 border-t border-line px-4 py-2.5">
          {b.reason_codes.map((rc) => (
            <Chip key={rc} tone={rc.startsWith("HARD_FAIL") ? "warn" : "quiet"}>
              {rc}
            </Chip>
          ))}
          <Chip>
            band {b.triage.band_source} / rule {b.triage.rule_class}
          </Chip>
          {b.triage.urgency_signals.map((u) => (
            <Chip key={u}>{u}</Chip>
          ))}
        </div>
      </section>

      {/* 3+4. claims table and URL report cards */}
      <BundleTabs bundle={b} />

      {/* 8. action bar */}
      <section aria-labelledby="action-h" className="rounded border border-line bg-card">
        <h2 id="action-h" className="sr-only">
          Actions
        </h2>
        <div className="flex flex-wrap items-center gap-2 px-4 py-3">
          {closed ? (
            <span className="text-sm text-fg-muted">closed, audit written</span>
          ) : (
            <>
              <button
                type="button"
                className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-bg hover:opacity-90 disabled:opacity-50"
                disabled={decide.isPending}
                onClick={() =>
                  decide.mutate(
                    b.recommended_action === "warn_member" ? "warn_member" : "verify_with_issuer",
                  )
                }
              >
                {copyFor(locale, "case_action_approve")}
                {b.recommended_action ? `: ${b.recommended_action}` : ""}
              </button>
              <button
                type="button"
                className="rounded border border-line px-3 py-1.5 text-sm hover:bg-card-muted disabled:opacity-50"
                disabled={decide.isPending}
                onClick={() => decide.mutate("warn_member")}
              >
                {copyFor(locale, "case_action_warn")}
              </button>
              <button
                type="button"
                className="rounded border border-line px-3 py-1.5 text-sm text-fg-muted hover:bg-card-muted hover:text-fg disabled:opacity-50"
                disabled={decide.isPending}
                onClick={() => decide.mutate("allow")}
              >
                Allow
              </button>
            </>
          )}
        </div>
      </section>
    </div>
  );
}

function ResultIcon({ result }: { result: CheckResult }) {
  if (result === "PASS")
    return (
      <span className="inline-flex text-safe-fg" title="PASS">
        <Check size={14} aria-hidden />
        <span className="sr-only">PASS</span>
      </span>
    );
  if (result === "FAIL")
    return (
      <span className="inline-flex text-scam-fg" title="FAIL">
        <X size={14} aria-hidden />
        <span className="sr-only">FAIL</span>
      </span>
    );
  return (
    <span className="inline-flex text-fg-subtle" title="INCONCLUSIVE">
      <Minus size={14} aria-hidden />
      <span className="sr-only">INCONCLUSIVE</span>
    </span>
  );
}

function FindingsTable({ findings }: { findings: VerificationFinding[] }) {
  if (findings.length === 0) {
    return (
      <p className="px-4 py-6 text-center text-sm text-fg-muted">
        No registry claims in this signal; nothing to adjudicate.
      </p>
    );
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-line text-left text-xs text-fg-muted">
          <th scope="col" className="px-4 py-2 font-medium">Subject</th>
          <th scope="col" className="px-4 py-2 font-medium">Check</th>
          <th scope="col" className="px-4 py-2 font-medium">Result</th>
          <th scope="col" className="px-4 py-2 font-medium">Weight</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-line">
        {findings.map((f, i) => (
          <tr key={i} className="align-top">
            <td className="max-w-56 truncate px-4 py-2 font-mono text-xs">{f.subject}</td>
            <td className="px-4 py-2 font-mono text-xs text-fg-muted">{f.check_type}</td>
            <td className="px-4 py-2">
              <ResultIcon result={f.result} />
            </td>
            <td className="px-4 py-2 font-mono text-xs tabular-nums">{f.weight.toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function BundleTabs({ bundle }: { bundle: EvidenceBundle }) {
  const { locale } = useLocale();
  const tabCls = "px-3 py-1.5 text-xs border-b-2 -mb-px data-[state=active]:border-accent data-[state=active]:text-fg text-fg-muted hover:text-fg";
  return (
    <Tabs.Root defaultValue="findings" className="rounded border border-line bg-card">
      <Tabs.List aria-label={copyFor(locale, "case_bundle")} className="flex gap-1 border-b border-line px-2">
        <Tabs.Trigger value="findings" className={tabCls}>
          {copyFor(locale, "case_findings")}
        </Tabs.Trigger>
        <Tabs.Trigger value="graph" className={tabCls}>
          {copyFor(locale, "case_graph")}
        </Tabs.Trigger>
        <Tabs.Trigger value="timeline" className={tabCls}>
          {copyFor(locale, "case_timeline")}
        </Tabs.Trigger>
        <Tabs.Trigger value="engagement" className={tabCls}>
          {copyFor(locale, "case_engagement")}
        </Tabs.Trigger>
        <Tabs.Trigger value="cost" className={tabCls}>
          {copyFor(locale, "case_cost")}
        </Tabs.Trigger>
      </Tabs.List>

      <Tabs.Content value="findings" className="py-1 focus:outline-none">
        <FindingsTable findings={bundle.findings} />
      </Tabs.Content>

      <Tabs.Content value="graph" className="p-4 focus:outline-none">
        {bundle.graph.unavailable ? (
          <Banner tone="degraded" title="GRAPH_UNAVAILABLE" body="graph dependency was down during this investigation" />
        ) : bundle.graph.identifiers.length === 0 ? (
          <p className="text-sm text-fg-muted">No correlatable identifiers in this signal.</p>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-1.5">
              {bundle.graph.identifiers.map((id, i) => (
                <HashChip key={i} value={id.hashed_value} label={id.kind} />
              ))}
            </div>
            <div className="flex gap-6 font-mono text-xs text-fg-muted tabular-nums">
              <span>prior events {bundle.graph.prior_events}</span>
              <span>max taint {bundle.graph.max_taint.toFixed(2)}</span>
            </div>
            <p className="text-[11px] text-fg-subtle">
              Network memory: hashes are keyed, never reversible; coverage note rides in every bundle.
            </p>
          </div>
        )}
      </Tabs.Content>

      <Tabs.Content value="timeline" className="p-4 focus:outline-none">
        <ol className="space-y-2">
          {bundle.trace.spans.map((s) => (
            <li key={s.stage} className="flex items-center gap-3 text-sm">
              <span className="w-20 font-mono text-xs text-fg-muted">{s.stage}</span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-line">
                <span
                  className={`block h-full ${s.status === "ok" ? "bg-fg-subtle" : "bg-wary-fg"}`}
                  style={{ width: `${Math.min(100, (s.ms / bundle.trace.total_ms) * 100)}%` }}
                />
              </span>
              <span className="w-16 text-right font-mono text-xs tabular-nums">{s.ms} ms</span>
            </li>
          ))}
          <li className="pt-1 font-mono text-xs text-fg-subtle tabular-nums">
            total {bundle.trace.total_ms} ms
          </li>
        </ol>
      </Tabs.Content>

      <Tabs.Content value="engagement" className="p-4 focus:outline-none">
        {bundle.engagement ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Chip tone={bundle.engagement.outcome === "CONFIRMED_SCAM" ? "warn" : "quiet"}>
                {bundle.engagement.outcome}
              </Chip>
              <span className="font-mono text-[11px] text-fg-subtle">
                stop: {bundle.engagement.stop_reason}
              </span>
            </div>
            <ol className="space-y-2">
              {bundle.engagement.turns.map((t, i) => (
                <li
                  key={i}
                  className={`max-w-[85%] rounded border px-3 py-2 text-sm ${
                    t.role === "engage_agent"
                      ? "border-line bg-card-muted"
                      : "ml-auto border-scam-line bg-scam-bg text-scam-fg"
                  }`}
                >
                  {t.text}
                  <span className="mt-1 block font-mono text-[10px] text-fg-subtle">
                    +{t.offset_s}s
                  </span>
                </li>
              ))}
            </ol>
          </div>
        ) : (
          <p className="text-sm text-fg-muted">Not engaged; this case resolved on evidence alone.</p>
        )}
      </Tabs.Content>

      <Tabs.Content value="cost" className="p-4 focus:outline-none">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-fg-muted">
              <th scope="col" className="py-2 font-medium">Stage</th>
              <th scope="col" className="py-2 font-medium">Model</th>
              <th scope="col" className="py-2 font-medium">Tokens in/out</th>
              <th scope="col" className="py-2 text-right font-medium">USD</th>
            </tr>
          </thead>
          <tbody>
            {bundle.cost.entries.map((e, i) => (
              <tr key={i} className="border-b border-line last:border-b-0">
                <td className="py-2 font-mono text-xs">{e.stage}</td>
                <td className="py-2 font-mono text-xs text-fg-muted">{e.model_id}</td>
                <td className="py-2 font-mono text-xs tabular-nums">
                  {e.input_tokens} / {e.output_tokens}
                </td>
                <td className="py-2 text-right font-mono text-xs tabular-nums">
                  ${e.usd.toFixed(6)}
                </td>
              </tr>
            ))}
            <tr>
              <td colSpan={3} className="py-2 text-right text-xs text-fg-muted">
                total
              </td>
              <td className="py-2 text-right font-mono text-xs tabular-nums">
                ${bundle.cost.total_usd.toFixed(6)}
              </td>
            </tr>
          </tbody>
        </table>
      </Tabs.Content>
    </Tabs.Root>
  );
}
