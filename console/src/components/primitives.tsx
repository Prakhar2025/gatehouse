"use client";

/**
 * UI primitives (doc 10 section 4 build order, wave one). Every component
 * is deliberately quiet: 1px borders, no shadows except the popover, no
 * rounded-beyond-6px, tabular numbers everywhere numbers appear.
 */
import { useEffect, useState, useSyncExternalStore } from "react";
import type { Verdict } from "@/lib/api/schemas";
import { copyFor, useLocale, verdictCopyKey } from "@/lib/i18n";

const verdictStyle: Record<Verdict, string> = {
  SAFE: "bg-safe-bg text-safe-fg border-safe-line",
  SUSPICIOUS: "bg-wary-bg text-wary-fg border-wary-line",
  SCAM: "bg-scam-bg text-scam-fg border-scam-line",
  NEEDS_HUMAN: "bg-human-bg text-human-fg border-human-line",
};

export function VerdictBadge({ verdict, small }: { verdict: Verdict; small?: boolean }) {
  const { locale } = useLocale();
  return (
    <span
      className={`inline-flex items-center rounded border font-medium tracking-wide uppercase ${
        small ? "px-1.5 py-px text-[10px]" : "px-2 py-0.5 text-xs"
      } ${verdictStyle[verdict]}`}
    >
      {copyFor(locale, verdictCopyKey(verdict))}
    </span>
  );
}

export function Chip({ children, tone = "quiet" }: { children: React.ReactNode; tone?: "quiet" | "warn" }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-px font-mono text-[11px] ${
        tone === "warn"
          ? "border-scam-line bg-scam-bg text-scam-fg"
          : "border-line bg-card-muted text-fg-muted"
      }`}
    >
      {children}
    </span>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone =
    value >= 0.8 ? "bg-scam-fg" : value >= 0.55 ? "bg-wary-fg" : "bg-fg-subtle";
  return (
    <span className="inline-flex items-center gap-2" title={`confidence ${pct} percent`}>
      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-line" aria-hidden>
        <span className={`block h-full ${tone}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="font-mono text-xs text-fg-muted tabular-nums">{pct}%</span>
    </span>
  );
}

export function HashChip({ value, label }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1200);
    return () => clearTimeout(t);
  }, [copied]);
  return (
    <button
      type="button"
      className="inline-flex items-center gap-1 rounded border border-line bg-card-muted px-1.5 py-px font-mono text-[11px] text-fg-muted hover:border-line-strong hover:text-fg"
      title={`copy ${label ?? "hash"}`}
      onClick={() => {
        void navigator.clipboard?.writeText(value).then(() => setCopied(true));
      }}
    >
      {value.slice(0, 10)}
      <span className="text-fg-subtle">{value.slice(10, 16)}</span>
      <span aria-live="polite">{copied ? "copied" : ""}</span>
    </button>
  );
}

const relativeLabel = (iso: string, nowMs: number): string => {
  const m = Math.max(0, Math.round((nowMs - new Date(iso).getTime()) / 60_000));
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  if (m < 1440) return `${Math.round(m / 60)}h ago`;
  return `${Math.round(m / 1440)}d ago`;
};

/**
 * One ticking clock shared by every TimeAgo. Read through useSyncExternalStore
 * so a prerendered page hydrates without a mismatch: the server snapshot is 0,
 * which renders the absolute moment, and the client swaps to real relative
 * time once subscribed.
 */
let clockNow = 0;
const clockListeners = new Set<() => void>();
let clockTimer: ReturnType<typeof setInterval> | null = null;

const subscribeClock = (onChange: () => void) => {
  clockListeners.add(onChange);
  if (clockTimer === null) {
    clockNow = Date.now();
    clockTimer = setInterval(() => {
      clockNow = Date.now();
      clockListeners.forEach((listener) => listener());
    }, 60_000);
  }
  return () => {
    clockListeners.delete(onChange);
    if (clockListeners.size === 0 && clockTimer !== null) {
      clearInterval(clockTimer);
      clockTimer = null;
    }
  };
};
const readClock = () => clockNow;
const readServerClock = () => 0;

export function TimeAgo({ iso }: { iso: string }) {
  // The clock has to be the real one: measuring live cases against the fixed
  // mock clock rendered week-old cases as "just now", which is a page telling
  // the reader something false. Date.now() cannot be read during render in a
  // prerendered page without a hydration mismatch, so the first paint shows
  // the absolute moment and the relative label arrives after mount.
  const nowMs = useSyncExternalStore(subscribeClock, readClock, readServerClock);
  const label =
    nowMs === 0
      ? new Date(iso).toISOString().slice(0, 16).replace("T", " ") + "Z"
      : relativeLabel(iso, nowMs);
  return (
    <time dateTime={iso} className="font-mono text-xs text-fg-muted tabular-nums" title={iso}>
      {label}
    </time>
  );
}

export function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded border border-line bg-card px-3 py-2.5">
      <div className="text-xs text-fg-muted">{label}</div>
      <div className="mt-0.5 font-mono text-lg leading-6 tabular-nums">{value}</div>
      {sub ? <div className="mt-0.5 font-mono text-[11px] text-fg-subtle tabular-nums">{sub}</div> : null}
    </div>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded border border-dashed border-line bg-card-muted px-6 py-16 text-center">
      <div className="max-w-md">
        <div className="text-sm font-medium">{title}</div>
        <p className="mt-1.5 text-sm text-fg-muted">{body}</p>
        {action ? <div className="mt-4">{action}</div> : null}
      </div>
    </div>
  );
}

export function Banner({
  tone,
  title,
  body,
  action,
}: {
  tone: "degraded" | "error" | "info";
  title: string;
  body?: string;
  action?: React.ReactNode;
}) {
  const style =
    tone === "degraded"
      ? "border-wary-line bg-wary-bg text-wary-fg"
      : tone === "error"
        ? "border-scam-line bg-scam-bg text-scam-fg"
        : "border-line bg-card text-fg";
  return (
    <div className={`flex flex-wrap items-center justify-between gap-2 rounded border px-3 py-2 text-sm ${style}`} role="status">
      <div>
        <span className="font-medium">{title}</span>
        {body ? <span className="opacity-80"> {body}</span> : null}
      </div>
      {action}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-line ${className ?? "h-4 w-full"}`} />;
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-line bg-card px-1 font-mono text-[10px] text-fg-muted">
      {children}
    </kbd>
  );
}
