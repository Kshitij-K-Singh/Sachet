import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { makeT, type Lang } from "./i18n";
import {
  CONTRASTS,
  FONT_SCALES,
  PrefsContext,
  THEMES,
  type Contrast,
  type FontScale,
  type Prefs,
  type Theme,
} from "./prefs-context";

const THEME_KEY = "sachet.theme";
const LANG_KEY = "sachet.lang";
const FONT_KEY = "sachet.font";
const CONTRAST_KEY = "sachet.contrast";

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
  const [fontScale, setFontScale] = useState<FontScale>(
    () => readStored(FONT_KEY, FONT_SCALES, "default") as FontScale
  );
  const [contrast, setContrastState] = useState<Contrast>(
    () => readStored(CONTRAST_KEY, CONTRASTS, "default") as Contrast
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

  useEffect(() => {
    // data-font drives the text-size scale (A- / A / A+). Stored so a low-vision
    // user does not have to re-enlarge on every visit.
    document.documentElement.dataset.font = fontScale;
    store(FONT_KEY, fontScale);
  }, [fontScale]);

  useEffect(() => {
    // data-contrast drives default / high-contrast / grayscale. High contrast is
    // for low vision; grayscale is the colour-blindness aid.
    document.documentElement.dataset.contrast = contrast;
    store(CONTRAST_KEY, contrast);
  }, [contrast]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }, []);

  const setLang = useCallback((next: Lang) => setLangState(next), []);

  const decreaseFont = useCallback(() => {
    setFontScale((prev) => {
      const i = FONT_SCALES.indexOf(prev);
      return FONT_SCALES[Math.max(0, i - 1)];
    });
  }, []);

  const resetFont = useCallback(() => setFontScale("default"), []);

  const increaseFont = useCallback(() => {
    setFontScale((prev) => {
      const i = FONT_SCALES.indexOf(prev);
      return FONT_SCALES[Math.min(FONT_SCALES.length - 1, i + 1)];
    });
  }, []);

  const setContrast = useCallback((next: Contrast) => setContrastState(next), []);

  const t = useMemo(() => makeT(lang), [lang]);

  const value = useMemo<Prefs>(
    () => ({
      theme,
      toggleTheme,
      lang,
      setLang,
      fontScale,
      decreaseFont,
      resetFont,
      increaseFont,
      contrast,
      setContrast,
      t,
    }),
    [
      theme,
      toggleTheme,
      lang,
      setLang,
      fontScale,
      decreaseFont,
      resetFont,
      increaseFont,
      contrast,
      setContrast,
      t,
    ]
  );

  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}