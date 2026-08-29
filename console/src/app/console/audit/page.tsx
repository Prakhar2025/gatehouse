"use client";

import { useQuery } from "@tanstack/react-query";
import { Link2 } from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "@/lib/api/client";
import { copyFor, useLocale } from "@/lib/i18n";
import { Chip, EmptyState, Skeleton, TimeAgo } from "@/components/primitives";

const EVENT_TYPES = ["all", "case.received", "verdict.composed", "escalation.notified"];

export default function AuditPage() {
  const { locale } = useLocale();
  const audit = useQuery({ queryKey: ["audit"], queryFn: () => api().getAudit() });
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");

  const entries = useMemo(() => {
    const all = audit.data ?? [];
    return all.filter(
      (e) =>
        (filter === "all" || e.event_type === filter) &&
        (query === "" ||
          e.summary.toLowerCase().includes(query.toLowerCase()) ||
          (e.case_id ?? "").includes(query)),
    );
  }, [audit.data, filter, query]);

  return (
    <div className="mx-auto max-w-4xl space-y-3 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-base font-semibold tracking-tight">{copyFor(locale, "audit_title")}</h1>
        <span className="flex items-center gap-1 text-xs text-fg-muted">
          <Link2 size={12} aria-hidden /> {copyFor(locale, "audit_chain")}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {EVENT_TYPES.map((t) => (
          <button
            key={t}
            type="button"
            aria-pressed={filter === t}
            className={`rounded border px-2 py-1 font-mono text-[11px] ${
              filter === t ? "border-accent bg-accent text-bg" : "border-line text-fg-muted hover:text-fg"
            }`}
            onClick={() => setFilter(t)}
          >
            {t}
          </button>
        ))}
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="filter by case id or text"
          aria-label="filter audit entries"
          className="ml-auto w-56 rounded border border-line bg-card px-2 py-1 text-sm"
        />
      </div>

      {audit.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-10" />
          ))}
        </div>
      ) : entries.length === 0 ? (
        <EmptyState
          title="No matching entries"
          body="Adjust the filter or clear the search to see the chain again."
        />
      ) : (
        <ol className="overflow-hidden rounded border border-line bg-card">
          {entries.map((e) => (
            <li
              key={e.seq}
              className="flex flex-col gap-1 border-b border-line px-4 py-2.5 last:border-b-0 sm:flex-row sm:items-center sm:gap-3"
            >
              <span className="w-10 shrink-0 font-mono text-[11px] text-fg-subtle tabular-nums">
                #{e.seq}
              </span>
              <Chip>{e.event_type}</Chip>
              <span className="min-w-0 flex-1 truncate text-sm">{e.summary}</span>
              <span className="shrink-0 text-xs text-fg-muted">{e.actor}</span>
              <TimeAgo iso={e.at} />
              <span
                className="hidden font-mono text-[10px] text-fg-subtle lg:inline"
                title={`hash ${e.hash} | prev ${e.prev_hash ?? "genesis"}`}
              >
                {e.hash.slice(0, 8)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
