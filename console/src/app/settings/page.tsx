"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Switch from "@radix-ui/react-switch";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { copyFor, useLocale, type Locale } from "@/lib/i18n";
import { Banner, Skeleton } from "@/components/primitives";

export default function SettingsPage() {
  const { locale, setLocale } = useLocale();
  const queryClient = useQueryClient();
  const household = useQuery({ queryKey: ["household"], queryFn: () => api().getHousehold() });
  // Local override until the (mock) PATCH round-trip lands; derived value
  // otherwise. No effect-synced state: server data flows down, intent flows up.
  const [override, setOverride] = useState<boolean | null>(null);
  const [saved, setSaved] = useState(false);

  const s = household.data?.settings;
  const engagement = override ?? s?.engagement_enabled ?? false;

  const patch = useMutation({
    mutationFn: (body: { engagement_enabled?: boolean; language?: Locale }) => {
      void body; // PATCH /v1/household/settings lands with the gateway
      return new Promise<void>((r) => setTimeout(r, 250));
    },
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
      void queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });

  const exportHousehold = useMutation({
    mutationFn: async () => {
      const data = await api().getHousehold();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${data.household_id}-export.json`;
      a.click();
      URL.revokeObjectURL(url);
    },
  });

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-4 md:p-6">
      <h1 className="text-base font-semibold tracking-tight">{copyFor(locale, "settings_title")}</h1>
      {saved ? <Banner tone="info" title="Saved" /> : null}

      {household.isLoading || !s ? (
        <div className="space-y-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      ) : (
        <>
          {/* Thresholds, read-only in v1 mock with plain-language effect */}
          <section className="rounded border border-line bg-card p-4">
            <h2 className="text-sm font-medium">Detection thresholds</h2>
            <dl className="mt-3 space-y-2 text-sm">
              {(
                [
                  ["Escalation floor", s.thresholds.escalation_floor, "signals above this reach you"],
                  ["Gray band low", s.thresholds.gray_band_low, "below this, silence is safe"],
                  ["Gray band high", s.thresholds.gray_band_high, "above this, act without asking"],
                ] as const
              ).map(([label, value, effect]) => (
                <div key={label} className="flex items-center justify-between gap-4">
                  <dt className="text-fg-muted">
                    {label}
                    <span className="block text-xs text-fg-subtle">{effect}</span>
                  </dt>
                  <dd className="font-mono text-sm tabular-nums">{value.toFixed(2)}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-[11px] text-fg-subtle">
              Thresholds are pack data calibrated on the dev split (doc 07); they change through
              evaluation, not sliders, so no tuned-on-a-hunch numbers ever reach production.
            </p>
          </section>

          {/* Quiet hours */}
          <section className="rounded border border-line bg-card p-4">
            <h2 className="text-sm font-medium">{copyFor(locale, "settings_quiet")}</h2>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
              <span className="font-mono tabular-nums">{s.quiet_hours.start}</span>
              <span className="text-fg-subtle">to</span>
              <span className="font-mono tabular-nums">{s.quiet_hours.end}</span>
              <Chip>{s.quiet_hours.timezone}</Chip>
            </div>
            <p className="mt-2 text-xs text-fg-muted">
              Escalations queue silently and flush as the morning digest; scams never wait.
            </p>
          </section>

          {/* Language */}
          <section className="rounded border border-line bg-card p-4">
            <h2 className="text-sm font-medium">{copyFor(locale, "settings_language")}</h2>
            <div className="mt-3 flex gap-2">
              {(["en", "hi"] as Locale[]).map((l) => (
                <button
                  key={l}
                  type="button"
                  aria-pressed={locale === l}
                  className={`rounded border px-3 py-1.5 text-sm ${
                    locale === l ? "border-accent bg-accent text-bg" : "border-line hover:bg-card-muted"
                  }`}
                  onClick={() => setLocale(l)}
                >
                  {l === "en" ? "English" : "हिन्दी"}
                </button>
              ))}
            </div>
          </section>

          {/* Engagement master toggle */}
          <section className="rounded border border-line bg-card p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-sm font-medium">{copyFor(locale, "settings_engagement")}</h2>
                <p className="mt-0.5 text-xs text-fg-muted">
                  Agent conversations with suspects run inside turn budgets; transcripts live in
                  every bundle.
                </p>
              </div>
              <Switch.Root
                checked={engagement}
                onCheckedChange={(v) => {
                  setOverride(v);
                  patch.mutate({ engagement_enabled: v });
                }}
                aria-label={copyFor(locale, "settings_engagement")}
                className="relative h-5 w-9 rounded-full border border-line bg-line transition-colors data-[state=checked]:bg-safe-fg"
              >
                <Switch.Thumb className="block h-4 w-4 translate-x-0.5 rounded-full bg-card shadow transition-transform data-[state=checked]:translate-x-[1.05rem]" />
              </Switch.Root>
            </div>
          </section>

          {/* Data controls */}
          <section className="rounded border border-line bg-card p-4">
            <h2 className="text-sm font-medium">Data controls</h2>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="rounded border border-line px-3 py-1.5 text-sm hover:bg-card-muted"
                onClick={() => exportHousehold.mutate()}
              >
                {copyFor(locale, "settings_export")}
              </button>
              <button
                type="button"
                className="rounded border border-scam-line px-3 py-1.5 text-sm text-scam-fg opacity-50"
                disabled
                title="requires typed confirmation and lands with the gateway"
              >
                Delete household
              </button>
            </div>
            <p className="mt-2 text-[11px] text-fg-subtle">
              Deletion runs as an audited cascade job with a completion certificate (doc 08).
            </p>
          </section>
        </>
      )}
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded border border-line bg-card-muted px-1.5 py-px font-mono text-[11px] text-fg-muted">
      {children}
    </span>
  );
}
