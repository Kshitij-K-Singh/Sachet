import { createContext, useContext } from "react";
import type { Lang } from "./i18n";

/* Context and hook live apart from the provider component on purpose: a module
   that exports both a component and plain functions defeats React Fast Refresh,
   which is enforced by react-refresh/only-export-components. Keeping the hook
   here leaves prefs.tsx exporting exactly one component. */

export type Theme = "dark" | "light";

export const THEMES: readonly Theme[] = ["dark", "light"];

/* Accessibility prefs, modelled on the SEBI / NSDL gov toolbar:
   text size (A- / A / A+) and contrast (default / high / grayscale).
   Grayscale is the colour-blindness aid: it removes colour as a signal so
   nothing on the page depends on red-vs-green alone. */
export type FontScale = "small" | "default" | "large" | "xlarge";

export const FONT_SCALES: readonly FontScale[] = ["small", "default", "large", "xlarge"];

export type Contrast = "default" | "high" | "grayscale";

export const CONTRASTS: readonly Contrast[] = ["default", "high", "grayscale"];

export type Prefs = {
  theme: Theme;
  toggleTheme: () => void;
  lang: Lang;
  setLang: (lang: Lang) => void;
  fontScale: FontScale;
  decreaseFont: () => void;
  resetFont: () => void;
  increaseFont: () => void;
  contrast: Contrast;
  setContrast: (c: Contrast) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

export const PrefsContext = createContext<Prefs | null>(null);

export function usePrefs(): Prefs {
  const ctx = useContext(PrefsContext);
  if (!ctx) throw new Error("usePrefs must be used inside <PrefsProvider>");
  return ctx;
}