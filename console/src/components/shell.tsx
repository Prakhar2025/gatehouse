"use client";

/**
 * ConsoleShell: sidebar navigation on desktop, bottom bar on phones
 * (guardians live on phones). Health feeds the degraded banner so a
 * degraded system can never look calm.
 */
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ClipboardList,
  LayoutDashboard,
  ScrollText,
  Settings,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api/client";
import { copyFor, useLocale } from "@/lib/i18n";

const NAV = [
  { href: "/", key: "nav_dashboard" as const, icon: LayoutDashboard },
  { href: "/queue", key: "nav_queue" as const, icon: ClipboardList },
  { href: "/circle", key: "nav_circle" as const, icon: Users },
  { href: "/settings", key: "nav_settings" as const, icon: Settings },
  { href: "/audit", key: "nav_audit" as const, icon: ScrollText },
];

export function ConsoleShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { locale } = useLocale();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api().getHealth(),
    refetchInterval: 60_000,
  });
  const degraded = health.data?.degraded ?? [];

  return (
    <div className="flex min-h-svh flex-col md:flex-row">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:border focus:border-line focus:bg-card focus:px-2 focus:py-1 focus:text-sm"
      >
        Skip to content
      </a>

      <aside className="hidden w-52 shrink-0 flex-col border-r border-line bg-card md:flex">
        <div className="border-b border-line px-4 py-4">
          <Link href="/" className="block">
            <div className="text-sm font-semibold tracking-tight">
              {copyFor(locale, "app_name")}
            </div>
            <div className="mt-0.5 text-[11px] leading-4 text-fg-muted">
              {copyFor(locale, "app_tagline")}
            </div>
          </Link>
        </div>
        <nav aria-label="Console" className="flex-1 space-y-0.5 p-2">
          {NAV.map(({ href, key, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-2.5 rounded px-2.5 py-1.5 text-sm ${
                  active ? "bg-bg font-medium text-fg" : "text-fg-muted hover:bg-bg hover:text-fg"
                }`}
              >
                <Icon size={15} strokeWidth={1.75} aria-hidden />
                {copyFor(locale, key)}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-line p-3">
          <div className="flex items-center gap-1.5 font-mono text-[11px] text-fg-subtle tabular-nums">
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${health.isError ? "bg-wary-fg" : "bg-safe-fg"}`}
              aria-hidden
            />
            api {health.data ? health.data.version : "offline"}
          </div>
          <Link href="/trust" className="mt-1 block text-[11px] text-fg-subtle hover:text-fg">
            Trust center
          </Link>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {degraded.length > 0 ? (
          <div
            className="flex items-center gap-2 border-b border-wary-line bg-wary-bg px-4 py-1.5 text-xs text-wary-fg"
            role="status"
          >
            <AlertTriangle size={13} aria-hidden />
            {copyFor(locale, "gate_degraded")}: {degraded.join(", ")}
          </div>
        ) : null}
        <main id="main" className="min-w-0 flex-1 pb-16 md:pb-0">
          {children}
        </main>
        <nav
          aria-label="Console"
          className="fixed inset-x-0 bottom-0 z-40 flex border-t border-line bg-card md:hidden"
        >
          {NAV.map(({ href, key, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] ${
                  active ? "text-fg" : "text-fg-muted"
                }`}
              >
                <Icon size={17} strokeWidth={1.75} aria-hidden />
                {copyFor(locale, key)}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
