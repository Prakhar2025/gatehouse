"use client";

/**
 * Live review: real cases from DynamoDB, guardian taps the truth. Every tap
 * is an override row; the weekly taxonomy consumes disagreements. This is
 * the label engine that scales past manual triage.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { useState } from "react";
import { EmptyState, Skeleton, VerdictBadge } from "@/components/primitives";

interface LiveCase {
  case_id: string;
  verdict: string | null;
  confidence: number | null;
  member_name: string;
  received_at: string;
  text: string;
  degraded_flags: string[];
}

export default function ReviewPage() {
  const queryClient = useQueryClient();
  const [filter] = useState<"all" | "wrong">("all");
  const cases = useQuery({
    queryKey: ["live-cases"],
    queryFn: async (): Promise<LiveCase[]> => {
      const r = await fetch("/api/cases");
      if (!r.ok) throw new Error("LIVE_READ_FAILED");
      return (await r.json()).cases;
    },
  });
  const counts = useQuery({
    queryKey: ["overrides"],
    queryFn: async (): Promise<{ total: number; disagreed: number }> => {
      const r = await fetch("/api/review");
      if (!r.ok) throw new Error("OVERRIDE_READ_FAILED");
      return r.json();
    },
  });

  const tap = useMutation({
    mutationFn: (input: { case_id: string; agree: boolean }) =>
      fetch("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }).then((r) => {
        if (!r.ok) throw new Error("OVERRIDE_WRITE_FAILED");
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["overrides"] });
    },
  });

  const list = cases.data ?? [];
  const shown = filter === "wrong" ? list.filter((c) => false) : list;

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-base font-semibold tracking-tight">Live review</h1>
          <p className="mt-0.5 text-xs text-fg-muted">
            Real cases from the running gate. Tap the truth; disagreements feed
            next week&apos;s fixes.
          </p>
        </div>
        <div className="flex items-center gap-3 font-mono text-xs text-fg-muted tabular-nums">
          <span>
            labelled <span className="text-fg">{counts.data?.total ?? 0}</span>
          </span>
          <span>
            flagged wrong <span className="text-wary-fg">{counts.data?.disagreed ?? 0}</span>
          </span>
        </div>
      </div>

      {cases.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : cases.isError ? (
        <EmptyState
          title="Could not reach the live table"
          body="The API route reads Dynamo with the local credential chain. Retry once the chain is available."
          action={
            <button
              type="button"
              className="rounded border border-line px-3 py-1.5 text-sm hover:bg-card-muted"
              onClick={() => void cases.refetch()}
            >
              Retry
            </button>
          }
        />
      ) : shown.length === 0 ? (
        <EmptyState
          title="No live cases yet"
          body="Forward messages from the household bot; they appear here seconds after the verdict."
        />
      ) : (
        <ul className="space-y-3">
          {shown.map((c) => (
            <li key={c.case_id} className="rounded border border-line bg-card">
              <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5 text-xs text-fg-muted">
                <VerdictBadge verdict={(c.verdict ?? "NEEDS_HUMAN") as never} small />
                <span className="font-mono">{c.case_id}</span>
                {c.confidence != null ? (
                  <span className="tabular-nums">{Math.round(c.confidence * 100)}%</span>
                ) : null}
                <span className="ml-auto">{c.member_name}</span>
                <span>{new Date(c.received_at).toLocaleString()}</span>
              </div>
              <p className="whitespace-pre-wrap px-4 py-3 text-sm leading-relaxed">
                {c.text || "(signal text lives in the bundle; text projection pending)"}
              </p>
              <div className="flex items-center justify-end gap-2 px-4 pb-3">
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 rounded border border-safe-line bg-safe-bg px-3 py-1.5 text-xs font-medium text-safe-fg hover:opacity-80"
                  disabled={tap.isPending}
                  onClick={() => tap.mutate({ case_id: c.case_id, agree: true })}
                >
                  <Check size={13} aria-hidden /> Verdict correct
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 rounded border border-scam-line bg-scam-bg px-3 py-1.5 text-xs font-medium text-scam-fg hover:opacity-80"
                  disabled={tap.isPending}
                  onClick={() => tap.mutate({ case_id: c.case_id, agree: false })}
                >
                  <X size={13} aria-hidden /> Verdict wrong
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
