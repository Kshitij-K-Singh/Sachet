import type { ReactElement } from "react";

interface LogoProps {
  /** Renders the tagline. Pass null in tight spots like the favicon. */
  tagline?: string | null;
  className?: string;
}

/* The mark: "the flagged rule."
 *
 * The previous logo was a Devanagari "स" set in Space Grotesk — which has no
 * Devanagari subset, so it silently rendered in whatever system font the
 * browser fell back to. Different on every machine, tofu where no Devanagari
 * font exists. Hence geometry instead of a glyph: this is now a drawing, not a
 * character, and it looks identical everywhere.
 *
 * What it draws, and why:
 *
 *  - The horizontal bar is the *shirorekha*, the headline rule that binds
 *    Devanagari letters together. It is the most recognisable thing about the
 *    script, and it is literally a line drawn over text.
 *  - The stem descending from the bar's left third is the Devanagari vertical
 *    stroke, and the flagpole.
 *  - The pennant hanging off the right end is a flag. This product flags
 *    claims, so the rule ends in a flag.
 *
 * A rule drawn across a line of text, ending in a flag. Three bold shapes, so
 * it survives down to 16px in a favicon.
 */
function Mark({ className }: { className?: string }): ReactElement {
  return (
    <span className={`sachet-mark${className ? ` ${className}` : ""}`} aria-hidden="true">
      <svg viewBox="0 0 24 24" width="100%" height="100%" focusable="false">
        {/* Rounded plate. Radius comes from the token so the app icon and the
            favicon stay on the same shape scale as every card. */}
        <rect x="0" y="0" width="24" height="24" rx="6" className="sachet-mark-plate" />
        {/* Foreground: bar + stem + pennant. */}
        <rect x="4.75" y="8.5" width="14.5" height="2.5" rx="1.25" className="sachet-mark-ink" />
        <rect x="7.5" y="8.5" width="2.5" height="8.75" rx="1.25" className="sachet-mark-ink" />
        <path d="M19.25 8.5 V15.75 L13.5 8.5 Z" className="sachet-mark-ink" />
      </svg>
    </span>
  );
}

export default function Logo({ tagline = "Promotion vs education analyzer", className }: LogoProps): ReactElement {
  return (
    <span className={`sachet-logo${className ? ` ${className}` : ""}`}>
      <Mark />
      <span className="sachet-word">
        {/* The wordmark is Latin and set in Space Grotesk, which is loaded, so
            it never depends on a fallback. The Devanagari idea lives in the
            mark's geometry instead of in a fragile glyph. */}
        <span className="sachet-word-name">Sachet</span>
        {tagline ? <span className="sachet-word-sub">{tagline}</span> : null}
      </span>
    </span>
  );
}

/** The same mark as a standalone SVG string, for the favicon. */
export const MARK_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">' +
  '<rect width="24" height="24" rx="6" fill="#e95a2b"/>' +
  '<rect x="4.75" y="8.5" width="14.5" height="2.5" rx="1.25" fill="#17100a"/>' +
  '<rect x="7.5" y="8.5" width="2.5" height="8.75" rx="1.25" fill="#17100a"/>' +
  '<path d="M19.25 8.5 V15.75 L13.5 8.5 Z" fill="#17100a"/>' +
  "</svg>";
