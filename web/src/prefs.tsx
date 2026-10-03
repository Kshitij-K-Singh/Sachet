import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { makeT, type Lang } from "./i18n";
import { PrefsContext, THEMES, type Prefs, type Theme } from "./prefs-context";

const THEME_KEY = "sachet.theme";
const LANG_KEY = "sachet.lang";

/* localStorage throws in private mode and wherever storage is blocked, so every
   access is guarded. An absent or invalid value falls back to the default
   rather than leaving the attribute off, which would render no theme at all. */
function readStored(key: string, allowed: readonly string[], fallback: string): string {
  try {
    const v = localStorage.getItem(key);
    return v && allowed.includes(v) ? v : fallback;
  } catch {
    return fallback;
  }
}

function store(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* the preference simply will not persist */
  }
}

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(
    () => readStored(THEME_KEY, THEMES, "dark") as Theme
  );
  const [lang, setLangState] = useState<Lang>(
    () => readStored(LANG_KEY, ["en", "hi"], "en") as Lang
  );

  useEffect(() => {
    // data-theme drives every colour token; data-lang reorders the font stack so
    // Devanagari leads when the interface itself is Hindi. index.html sets both
    // before first paint, so this only has to keep them in sync afterwards.
    document.documentElement.dataset.theme = theme;
    store(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dataset.lang = lang;
    store(LANG_KEY, lang);
  }, [lang]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }, []);

  const setLang = useCallback((next: Lang) => setLangState(next), []);

  const t = useMemo(() => makeT(lang), [lang]);

  const value = useMemo<Prefs>(
    () => ({ theme, toggleTheme, lang, setLang, t }),
    [theme, toggleTheme, lang, setLang, t]
  );

  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}