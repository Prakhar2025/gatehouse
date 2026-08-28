"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Locale } from "@/lib/i18n";

interface LocaleState {
  locale: Locale;
  setLocale: (l: Locale) => void;
}

export const useLocaleStore = create<LocaleState>()(
  persist(
    (set) => ({
      locale: "en",
      setLocale: (locale) => set({ locale }),
    }),
    { name: "gatehouse-locale" },
  ),
);

export function useLocale() {
  const locale = useLocaleStore((s) => s.locale);
  return { locale, setLocale: useLocaleStore((s) => s.setLocale) };
}
