"use client";

import { useQuery } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Copy, Printer } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { copyFor, useLocale } from "@/lib/i18n";
import { Chip, Skeleton, TimeAgo } from "@/components/primitives";

export default function CirclePage() {
  const { locale } = useLocale();
  const household = useQuery({ queryKey: ["household"], queryFn: () => api().getHousehold() });
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteCode, setInviteCode] = useState("X7KQ4M");

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-base font-semibold tracking-tight">{copyFor(locale, "circle_title")}</h1>
        <button
          type="button"
          className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-bg hover:opacity-90"
          onClick={() => setInviteOpen(true)}
        >
          {copyFor(locale, "circle_invite")}
        </button>
      </div>

      {household.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : household.data ? (
        <>
          <ul className="grid gap-3 sm:grid-cols-2">
            {household.data.members.map((m) => (
              <li key={m.member_id} className="rounded border border-line bg-card p-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">{m.display_name}</div>
                  <Chip>{m.role}</Chip>
                </div>
                <div className="mt-2 space-y-1 text-xs text-fg-muted">
                  {m.bindings.map((b, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <span
                        className={`inline-block h-1.5 w-1.5 rounded-full ${
                          b.status === "bound" ? "bg-safe-fg" : "bg-wary-fg"
                        }`}
                        aria-hidden
                      />
                      {b.channel}: {b.status}
                    </div>
                  ))}
                </div>
                <div className="mt-2 flex items-center justify-between text-xs">
                  <span className={m.engagement_consent ? "text-fg-muted" : "text-wary-fg"}>
                    engagement consent: {m.engagement_consent ? "granted" : "not granted"}
                  </span>
                  {m.warning_count_30d > 0 ? (
                    <span className="font-mono text-[11px] text-wary-fg tabular-nums">
                      {m.warning_count_30d} warnings / 30d
                    </span>
                  ) : null}
                </div>
                {m.last_signal_at ? (
                  <div className="mt-1.5 text-xs text-fg-subtle">
                    last signal <TimeAgo iso={m.last_signal_at} />
                  </div>
                ) : null}
              </li>
            ))}
          </ul>

          {/* Invite ledger */}
          <section aria-labelledby="inv-h" className="rounded border border-line bg-card">
            <h2 id="inv-h" className="border-b border-line px-4 py-2.5 text-xs font-medium text-fg-muted">
              Invite codes
            </h2>
            <ul className="divide-y divide-line">
              {household.data.invites.map((inv) => (
                <li key={inv.invite_id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                  <span className="font-mono">{inv.code}</span>
                  <span className="flex items-center gap-3 text-xs text-fg-muted">
                    {inv.status}
                    <TimeAgo iso={inv.created_at} />
                  </span>
                </li>
              ))}
            </ul>
          </section>

          {/* Panic-button explainer, printable for elders */}
          <section className="rounded border border-line bg-card p-4 print:border-0">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-medium text-fg-muted">Panic card</h2>
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded border border-line px-2 py-1 text-xs hover:bg-card-muted"
                onClick={() => window.print()}
              >
                <Printer size={12} aria-hidden /> Print for elders
              </button>
            </div>
            <div className="mt-3 rounded border border-dashed border-line p-4 text-sm">
              <p className="font-medium">If a message frightens you</p>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-fg-muted">
                <li>Do not pay. Do not share any OTP.</li>
                <li>Forward the message to the Gatehouse bot here.</li>
                <li>Call a family member before acting. Waiting is safe.</li>
              </ol>
            </div>
          </section>
        </>
      ) : null}

      <Dialog.Root open={inviteOpen} onOpenChange={setInviteOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(24rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded border border-line bg-card p-4 focus:outline-none">
            <Dialog.Title className="text-sm font-semibold">
              {copyFor(locale, "circle_invite")}
            </Dialog.Title>
            <Dialog.Description className="mt-1 text-xs text-fg-muted">
              Member messages the bot /start CODE. Codes are single use.
            </Dialog.Description>
            <div className="mt-3 flex items-center justify-between rounded border border-line bg-card-muted px-3 py-2">
              <span className="font-mono text-lg tracking-widest">{inviteCode}</span>
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded border border-line px-2 py-1 text-xs hover:bg-bg"
                onClick={() => void navigator.clipboard?.writeText(inviteCode)}
              >
                <Copy size={12} aria-hidden /> Copy
              </button>
            </div>
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-bg hover:opacity-90"
                onClick={() => {
                  setInviteCode(
                    Array.from({ length: 6 }, () =>
                      "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"[Math.floor(Math.random() * 32)],
                    ).join(""),
                  );
                }}
              >
                Mint new code
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
