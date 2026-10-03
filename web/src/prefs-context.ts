import { createContext, useContext } from "react";
import type { Lang } from "./i18n";

/* Context and hook live apart from the provider component on purpose: a module
   that exports both a component and plain functions defeats React Fast Refresh,
   which is enforced by react-refresh/only-export-components. Keeping the hook
   here leaves prefs.tsx exporting exactly one component. */

export type Theme = "dark" | "light";

export const THEMES: readonly Theme[] = ["dark", "light"];

export type Prefs = {
  theme: Theme;
  toggleTheme: () => void;
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

export const PrefsContext = createContext<Prefs | null>(null);

export function usePrefs(): Prefs {
  const ctx = useContext(PrefsContext);
  if (!ctx) throw new Error("usePrefs must be used inside <PrefsProvider>");
  return ctx;
}