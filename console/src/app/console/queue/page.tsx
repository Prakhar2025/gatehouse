"use client";

/**
 * Decision queue, the work surface (doc 10 section 3). Keyboard-first:
 * j/k move, o or Enter opens, a approves the recommended action, w opens
 * the warn composer, Escape returns to dashboard, ? shows the map. Bulk
 * actions are deliberately absent: fraud review is not email.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { AlertTriangle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { copyFor, useLocale } from "@/lib/i18n";
import {
  Banner,
  ConfidenceBar,
  EmptyState,
  Kbd,
  Skeleton,
  TimeAgo,
  VerdictBadge,
} from "@/components/primitives";

const RANK: Record<string, number> = { NEEDS_HUMAN: 0, SCAM: 1, SUSPICIOUS: 2 };

export default function QueuePage() {
  const { locale } = useLocale();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState(0);
  const [warnFor, setWarnFor] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const queue = useQuery({
    queryKey: ["queue", "all"],
    queryFn: () => api().listCases(),
    refetchInterval: 15_000,
  });

  const cases = (queue.data?.cases ?? [])
    .filter((c) => c.state === "ESCALATED")
    .sort(
      (a, b) =>
        (RANK[a.verdict ?? ""] ?? 3) - (RANK[b.verdict ?? ""] ?? 3) ||
        new Date(a.received_at).getTime() - new Date(b.received_at).getTime(),
    );

  const approve = useMutation({
    mutationFn: (caseId: string) => {
      const c = cases.find((x) => x.case_id === caseId);
      const action = c?.recommended_action === "warn_member" ? "warn_member" : "allow";
      return api().postDecision(caseId, { action });
    },
    onSuccess: () => {
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["queue"] });
      void queryClient.invalidateQueries({ queryKey: ["metrics"] });
    },
    onError: (err) => {
      setActionError(err instanceof ApiError ? err.code : "NETWORK_ERROR");
    },
  });

  useEffect(() => {
    const node = listRef.current;
    if (!node) return;
    const active = node.querySelector<HTMLLIElement>(`[data-idx="${selected}"]`);
    active?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  const onKey = (e: React.KeyboardEvent) => {
    if (warnFor) return;
    if (e.key === "j" || e.key === "ArrowDown") {
      e.preventDefault();
      setSelected((s) => Math.min(cases.length - 1, s + 1));
    } else if (e.key === "k" || e.key === "ArrowUp") {
      e.preventDefault();
      setSelected((s) => Math.max(0, s - 1));
    } else if (e.key === "Enter" || e.key === "o") {
      const c = cases[selected];
      if (c) {
        e.preventDefault();
        router.push(`/console/cases/${c.case_id}`);
      }
    } else if (e.key === "a") {
      const c = cases[selected];
      if (c?.recommended_action) {
        e.preventDefault();
        approve.mutate(c.case_id);
      }
    } else if (e.key === "w") {
      const c = cases[selected];
      if (c) {
        e.preventDefault();
        setWarnFor(c.case_id);
      }
    } else if (e.key === "Escape") {
      router.push("/console");
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-3 p-4 md:p-6" onKeyDown={onKey} tabIndex={-1}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-base font-semibold tracking-tight">{copyFor(locale, "queue_title")}</h1>
        <p className="hidden items-center gap-1 text-xs text-fg-muted sm:flex" aria-hidden>
          <Kbd>j</Kbd>
          <Kbd>k</Kbd> move <Kbd>Enter</Kbd> open <Kbd>a</Kbd> approve <Kbd>w</Kbd> warn{" "}
          <Kbd>Esc</Kbd> back
        </p>
      </div>
      <p className="sr-only">{copyFor(locale, "queue_ranked")}</p>

      {actionError ? (
        <Banner
          tone="error"
          title={`${copyFor(locale, "common_error_title")}: ${actionError}`}
          action={
            <button
              type="button"
              className="rounded border border-scam-line px-2 py-0.5 text-xs"
              onClick={() => setActionError(null)}
            >
              {copyFor(locale, "common_retry")}
            </button>
          }
        />
      ) : null}

      {queue.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      ) : cases.length === 0 ? (
        <EmptyState
          title={copyFor(locale, "queue_empty_title")}
          body={copyFor(locale, "queue_empty_body")}
        />
      ) : (
        <ul
          ref={listRef}
          role="listbox"
          aria-label={copyFor(locale, "queue_title")}
          aria-activedescendant={`queue-row-${cases[selected]?.case_id ?? ""}`}
          className="overflow-hidden rounded border border-line bg-card"
        >
          {cases.map((c, i) => (
            <li
              key={c.case_id}
              id={`queue-row-${c.case_id}`}
              data-idx={i}
              role="option"
              aria-selected={i === selected}
              tabIndex={i === selected ? 0 : -1}
              onClick={() => setSelected(i)}
              onDoubleClick={() => router.push(`/console/cases/${c.case_id}`)}
              className={`flex cursor-pointer flex-col gap-1 border-b border-line px-4 py-3 last:border-b-0 sm:flex-row sm:items-center sm:gap-3 ${
                i === selected ? "bg-card-muted" : ""
              } ${i === selected ? "sm:border-l-2 sm:border-l-accent sm:pl-3.5" : ""}`}
            >
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <VerdictBadge verdict={c.verdict ?? "NEEDS_HUMAN"} small />
                <span className="min-w-0 flex-1 truncate text-sm">
                  {c.why_line}
                  {c.degraded_flags.length > 0 ? (
                    <span className="ml-2 inline-flex items-center gap-1 align-middle text-[11px] text-wary-fg">
                      <AlertTriangle size={11} aria-hidden />
                      {c.degraded_flags.join(", ")}
                    </span>
                  ) : null}
                </span>
              </div>
              <div className="flex shrink-0 items-center gap-3 pl-8 text-xs text-fg-muted sm:pl-0">
                <ConfidenceBar value={c.confidence ?? 0} />
                <span className="w-16 truncate">{c.member_name}</span>
                <TimeAgo iso={c.received_at} />
              </div>
            </li>
          ))}
        </ul>
      )}

      <WarnComposer caseId={warnFor} onClose={() => setWarnFor(null)} />
    </div>
  );
}

function WarnComposer({ caseId, onClose }: { caseId: string | null; onClose: () => void }) {
  const { locale } = useLocale();
  const queryClient = useQueryClient();
  const warn = useMutation({
    mutationFn: (input: { caseId: string; note: string }) =>
      api().postDecision(caseId ?? "", { action: "warn_member", note: input.note }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["queue"] });
      onClose();
    },
  });
  return (
    <Dialog.Root open={caseId !== null} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded border border-line bg-card p-4 shadow-lg focus:outline-none">
          <Dialog.Title className="text-sm font-semibold">
            {copyFor(locale, "case_action_warn")}
          </Dialog.Title>
          <Dialog.Description className="mt-1 text-xs text-fg-muted">
            {caseId}
          </Dialog.Description>
          <textarea
            className="mt-3 h-24 w-full resize-none rounded border border-line bg-bg p-2 text-sm"
            placeholder={copyFor(locale, "case_action_warn") + "..."}
            defaultValue={
              locale === "hi"
                ? "यह संदेश धोखाधड़ी के संकेत दिखाता है। भुगतान या OTP साझा न करें।"
                : "This message shows fraud signals. Do not pay or share OTPs."
            }
            id="warn-note"
          />
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              className="rounded border border-line px-2.5 py-1 text-sm text-fg-muted hover:text-fg"
              onClick={onClose}
            >
              Esc
            </button>
            <button
              type="button"
              className="rounded bg-accent px-2.5 py-1 text-sm font-medium text-bg hover:opacity-90"
              disabled={warn.isPending}
              onClick={() => {
                const note = (document.getElementById("warn-note") as HTMLTextAreaElement).value;
                if (caseId) warn.mutate({ caseId, note });
              }}
            >
              {warn.isPending ? "..." : copyFor(locale, "case_action_warn")}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
