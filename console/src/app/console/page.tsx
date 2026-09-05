"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { copyFor, useLocale } from "@/lib/i18n";
import { Banner, Skeleton, Stat, TimeAgo, VerdictBadge } from "@/components/primitives";

const VERDICT_WIDTH: Record<string, string> = {
  SAFE: "bg-safe-fg/70",
  SUSPICIOUS: "bg-wary-fg/80",
  SCAM: "bg-scam-fg/80",
  NEEDS_HUMAN: "bg-human-fg/80",
};

export default function DashboardPage() {
  const { locale } = useLocale();
  const health = useQuery({ queryKey: ["health"], queryFn: () => api().getHealth() });
  const metrics = useQuery({ queryKey: ["metrics"], queryFn: () => api().getMetrics() });
  const queue = useQuery({
    queryKey: ["queue", "escalated"],
    queryFn: () => api().listCases({ state: "ESCALATED" }),
    refetchInterval: 15_000,
  });
  const household = useQuery({ queryKey: ["household"], queryFn: () => api().getHousehold() });

  const m = metrics.data;
  const open = queue.data?.cases ?? [];
  const topOpen = open[0];

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 md:p-6">
      <h1 className="text-base font-semibold tracking-tight">
        {copyFor(locale, "nav_dashboard")}
      </h1>

      {health.data && health.data.degraded.length > 0 ? (
        <Banner tone="degraded" title={copyFor(locale, "gate_degraded")} body={copyFor(locale, "gate_degraded_body")} />
      ) : null}

      {/* Hero: answers one question, does the gate need me today */}
      <section aria-labelledby="gate-hero" className="rounded border border-line bg-card">
        <h2 id="gate-hero" className="sr-only">
          Gate status
        </h2>
        {metrics.isLoading ? (
          <div className="space-y-2 p-5">
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-4 w-72" />
          </div>
        ) : m && open.length > 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-3 p-5">
            <div>
              <div className="text-sm font-semibold text-wary-fg">
                {copyFor(locale, "gate_needs_you")}
              </div>
              <p className="mt-0.5 text-sm text-fg-muted">
                {copyFor(locale, "gate_needs_you_body", { open: open.length })}
              </p>
              {topOpen ? (
                <p className="mt-2 max-w-xl truncate text-sm">
                  <VerdictBadge verdict={topOpen.verdict ?? "NEEDS_HUMAN"} small />{" "}
                  <span className="text-fg-muted">{topOpen.why_line}</span>
                </p>
              ) : null}
            </div>
            <Link
              href="/console/queue"
              className="inline-flex items-center gap-1.5 rounded bg-accent px-3 py-1.5 text-sm font-medium text-bg hover:opacity-90"
            >
              {copyFor(locale, "nav_queue")} <ArrowRight size={14} aria-hidden />
            </Link>
          </div>
        ) : m ? (
          <div className="p-5">
            <div className="text-sm font-semibold text-safe-fg">
              {copyFor(locale, "gate_all_clear")}
            </div>
            <p className="mt-0.5 text-sm text-fg-muted">
              {copyFor(locale, "gate_all_clear_body", {
                screened: m.screened_7d,
                silent: m.silent_7d,
              })}
            </p>
            <VerdictMix mix={m.verdict_mix_7d} total={m.screened_7d} />
          </div>
        ) : null}
      </section>

      {/* Metrics row with published confidence intervals */}
      <section aria-label="Metrics">
        {m ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label={copyFor(locale, "metric_screened")} value={String(m.screened_7d)} sub={`${m.silent_7d} silent`} />
            <Stat label={copyFor(locale, "metric_open")} value={String(m.escalations_open)} />
            <Stat
              label={copyFor(locale, "metric_latency")}
              value={`${(m.latency_p50_ms / 1000).toFixed(1)}s`}
              sub={`p95 ${(m.latency_p95_ms / 1000).toFixed(1)}s`}
            />
            <Stat
              label={copyFor(locale, "metric_spend")}
              value={`$${m.spend_mean_usd.toFixed(5)}`}
              sub={`$${m.spend_7d_usd.toFixed(4)} / 7d`}
            />
            <Stat
              label={copyFor(locale, "metric_precision")}
              value={m.precision.toFixed(2)}
              sub={`CI ${m.precision_ci[0].toFixed(3)} to ${m.precision_ci[1].toFixed(3)}`}
            />
            <Stat
              label={copyFor(locale, "metric_false_gate")}
              value={`${(m.false_gate_rate * 100).toFixed(1)}%`}
              sub={`CI ${m.false_gate_ci[0].toFixed(3)} to ${m.false_gate_ci[1].toFixed(3)}`}
            />
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Weekly trend, hand-rolled SVG-free bars, no chart library weight */}
        <section aria-labelledby="trend-h" className="rounded border border-line bg-card p-4">
          <h2 id="trend-h" className="text-xs font-medium text-fg-muted">
            Volume, 7 days
          </h2>
          {m ? (
            <div className="mt-3 flex h-24 items-end gap-2" role="img" aria-label="cases per day this week">
              {m.trend_7d.map((d) => {
                const max = Math.max(...m.trend_7d.map((x) => x.cases));
                const h = Math.round((d.cases / max) * 100);
                const esc = Math.round((d.escalations / max) * 100);
                return (
                  <div key={d.day} className="flex flex-1 flex-col items-center gap-1">
                    <div className="relative flex h-24 w-full items-end">
                      <div className={`w-full ${VERDICT_WIDTH.SAFE}`} style={{ height: `${h}%` }} />
                      <div
                        className={`absolute bottom-0 w-full ${VERDICT_WIDTH.SUSPICIOUS}`}
                        style={{ height: `${esc}%` }}
                        title={`${d.escalations} escalations`}
                      />
                    </div>
                    <span className="font-mono text-[10px] text-fg-subtle tabular-nums">{d.day.split(" ")[1]}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <Skeleton className="mt-3 h-24" />
          )}
        </section>

        {/* Recent escalations */}
        <section aria-labelledby="recent-h" className="rounded border border-line bg-card">
          <h2 id="recent-h" className="border-b border-line px-4 py-2.5 text-xs font-medium text-fg-muted">
            Waiting on you
          </h2>
          {queue.isLoading ? (
            <div className="space-y-2 p-4">
              <Skeleton className="h-10" />
              <Skeleton className="h-10" />
              <Skeleton className="h-10" />
            </div>
          ) : open.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-fg-muted">
              {copyFor(locale, "queue_empty_title")}
            </p>
          ) : (
            <ul className="divide-y divide-line">
              {open.slice(0, 5).map((c) => (
                <li key={c.case_id}>
                  <Link
                    href={`/console/case?id=${c.case_id}`}
                    className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-card-muted"
                  >
                    <VerdictBadge verdict={c.verdict ?? "NEEDS_HUMAN"} small />
                    <span className="min-w-0 flex-1 truncate">{c.why_line}</span>
                    <span className="hidden shrink-0 text-xs text-fg-muted sm:inline">
                      {c.member_name}
                    </span>
                    <TimeAgo iso={c.received_at} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* Circle strip */}
      <section aria-labelledby="circle-h" className="rounded border border-line bg-card">
        <h2 id="circle-h" className="border-b border-line px-4 py-2.5 text-xs font-medium text-fg-muted">
          {household.data ? household.data.name : copyFor(locale, "nav_circle")}
        </h2>
        {household.data ? (
          <ul className="grid grid-cols-2 divide-line sm:grid-cols-4 sm:divide-x">
            {household.data.members.map((mem) => (
              <li key={mem.member_id} className="px-4 py-3">
                <div className="text-sm font-medium">{mem.display_name}</div>
                <div className="mt-0.5 flex items-center gap-1.5 text-xs text-fg-muted">
                  <span
                    className={`inline-block h-1.5 w-1.5 rounded-full ${
                      mem.bindings[0]?.status === "bound" ? "bg-safe-fg" : "bg-fg-subtle"
                    }`}
                    aria-hidden
                  />
                  telegram {mem.bindings[0]?.status}
                </div>
                {mem.last_signal_at ? (
                  <div className="mt-1 text-xs text-fg-subtle">
                    last signal <TimeAgo iso={mem.last_signal_at} />
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <div className="grid grid-cols-4 gap-2 p-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-14" />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function VerdictMix({
  mix,
  total,
}: {
  mix: { verdict: string; count: number }[];
  total: number;
}) {
  return (
    <div className="mt-4">
      <div className="flex h-2 w-full max-w-md overflow-hidden rounded-full border border-line">
        {mix.map((v) => (
          <div
            key={v.verdict}
            className={VERDICT_WIDTH[v.verdict]}
            style={{ width: `${(v.count / total) * 100}%` }}
            title={`${v.verdict}: ${v.count}`}
          />
        ))}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] text-fg-muted tabular-nums">
        {mix.map((v) => (
          <span key={v.verdict}>
            {v.verdict} {v.count}
          </span>
        ))}
      </div>
    </div>
  );
}
