"use client";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Skeleton, VerdictBadge } from "@/components/primitives";

/** Your week: the quiet-week story made checkable, straight from real cases. */
export default function DigestPage() {
  const digest = useQuery({
    queryKey: ["digest"],
    queryFn: async () => {
      const r = await fetch(`${BASE}/digest`);
      if (!r.ok) throw new Error("DIGEST_FAILED");
      return r.json() as Promise<{
        generated_at: string;
        cases: number;
        silent: number;
        escalations: { case_id: string; verdict: string; reason_codes: string[]; text: string; at: string }[];
      }>;
    },
  });

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div>
        <h1 className="font-display text-xl font-medium">Your week</h1>
        <p className="mt-1 text-xs text-fg-muted">
          The quiet-week story, computed live from the running gate. This is the
          same summary the morning digest sends to the guardian.
        </p>
      </div>

      {digest.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-20" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      ) : digest.data ? (
        <>
          <div className="rounded border border-line bg-card p-5">
            <div className="font-display text-2xl">
              {digest.data.cases} screened. {digest.data.silent} handled silently.
            </div>
            <div className="mt-1 text-sm text-fg-muted">
              {digest.data.escalations.length === 0
                ? "Nothing needed you this week."
                : `${digest.data.escalations.length} needed a decision, each with its evidence bundle below.`}
            </div>
          </div>
          {digest.data.escalations.map((e) => (
            <Link
              key={e.case_id}
              href={`/console/case?id=${e.case_id}`}
              className="block rounded border border-line bg-card p-4 transition hover:border-line-strong"
            >
              <div className="flex items-center gap-2">
                <VerdictBadge verdict={e.verdict as never} small />
                <span className="font-mono text-[10px] text-fg-subtle">{e.case_id}</span>
              </div>
              <p className="mt-2 line-clamp-2 break-words text-sm text-fg/80">{e.text}</p>
            </Link>
          ))}
        </>
      ) : null}
    </div>
  );
}
