import { CircleHalf, DropHalfBottom } from "@phosphor-icons/react";
import { CONTRASTS, FONT_SCALES } from "../prefs-context";
import { usePrefs } from "../prefs-context";

/* Gov-style accessibility strip, modelled on SEBI / NSDL:
   A- | A | A+ for text size, plus default / high-contrast / grayscale.
   Grayscale is the colour-blindness aid: with it on, no meaning is carried
   by colour alone (verdicts already carry text labels, and the meter keeps
   its LOW/MEDIUM/HIGH words). Everything persists to localStorage via prefs. */
export default function AccessibilityBar() {
  const {
    t,
    fontScale,
    decreaseFont,
    resetFont,
    increaseFont,
    contrast,
    setContrast,
  } = usePrefs();

  const fontIdx = FONT_SCALES.indexOf(fontScale);
  const atMin = fontIdx <= 0;
  const atMax = fontIdx >= FONT_SCALES.length - 1;

  const contrastLabel =
    contrast === "high"
      ? t("a11y.contrastHigh")
      : contrast === "grayscale"
        ? t("a11y.contrastGray")
        : t("a11y.contrastDefault");

  return (
    <div
      className="a11y-bar"
      role="toolbar"
      aria-label={t("a11y.toolbar")}
    >
      <div
        className="a11y-group"
        role="group"
        aria-label={t("a11y.textSize")}
      >
        <span className="a11y-group-label" aria-hidden="true">
          {t("a11y.textSize")}
        </span>
        <button
          type="button"
          className="a11y-btn a11y-btn-sm"
          onClick={decreaseFont}
          disabled={atMin}
          aria-label={t("a11y.decrease")}
          title={t("a11y.decrease")}
        >
          A−
        </button>
        <button
          type="button"
          className={`a11y-btn ${fontScale === "default" ? "is-on" : ""}`}
          onClick={resetFont}
          aria-label={t("a11y.reset")}
          title={t("a11y.reset")}
          aria-pressed={fontScale === "default"}
        >
          A
        </button>
        <button
          type="button"
          className="a11y-btn a11y-btn-lg"
          onClick={increaseFont}
          disabled={atMax}
          aria-label={t("a11y.increase")}
          title={t("a11y.increase")}
        >
          A+
        </button>
      </div>

      <span className="a11y-sep" aria-hidden="true" />

      <div
        className="a11y-group"
        role="group"
        aria-label={t("a11y.contrast")}
      >
        <span className="a11y-group-label" aria-hidden="true">
          {t("a11y.contrast")}
        </span>
        {CONTRASTS.map((c) => {
          const isOn = contrast === c;
          const label =
            c === "high"
              ? t("a11y.contrastHigh")
              : c === "grayscale"
                ? t("a11y.contrastGray")
                : t("a11y.contrastDefault");
          return (
            <button
              key={c}
              type="button"
              className={`a11y-btn a11y-contrast ${isOn ? "is-on" : ""} a11y-contrast-${c}`}
              onClick={() => setContrast(c)}
              aria-pressed={isOn}
              aria-label={label}
              title={label}
            >
              {c === "high" ? (
                <CircleHalf size={15} weight="fill" aria-hidden="true" />
              ) : c === "grayscale" ? (
                <DropHalfBottom size={15} weight="fill" aria-hidden="true" />
              ) : (
                <span aria-hidden="true" className="a11y-dot" />
              )}
              <span className="a11y-contrast-word">
                {c === "high" ? "HC" : c === "grayscale" ? "GS" : "STD"}
              </span>
            </button>
          );
        })}
      </div>

      {/* Screen-reader status so a change is announced without moving focus. */}
      <span className="sr-only" role="status" aria-live="polite">
        {t("a11y.announce", { font: fontScale, contrast: contrastLabel })}
      </span>
    </div>
  );
}
