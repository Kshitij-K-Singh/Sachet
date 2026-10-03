import { Fragment, useEffect, useRef } from "react";
import type { CSSProperties } from "react";

interface SplitTextProps {
  text: string;
  className?: string;
  baseDelay?: number;
  stagger?: number;
}

/* One grapheme cluster, not one UTF-16 code unit.
 *
 * `split("")` is wrong for this product's primary language. Devanagari builds
 * conjuncts and reorders matras across code points ("प्र" is प + ् + र), so
 * putting each code point in its own .split-char span hands the browser a
 * fragment it can no longer shape: the headline breaks and glyphs overlap.
 * Intl.Segmenter yields whole clusters, which shape correctly in isolation.
 * Where it is unavailable we animate whole words instead -- coarser, but never
 * mangled, which is the trade that matters. */
type SegmenterLike = {
  segment(input: string): Iterable<{ segment: string }>;
};

// Typed structurally rather than via `typeof Intl.Segmenter`: this project's
// tsconfig lib predates it, and widening the global lib for one call site would
// change type-checking for the whole app.
const Segmenter = (
  Intl as unknown as {
    Segmenter?: new (locales?: string, options?: { granularity?: string }) => SegmenterLike;
  }
).Segmenter;

function splitGraphemes(word: string): string[] {
  if (Segmenter) {
    const seg = new Segmenter(undefined, { granularity: "grapheme" });
    return Array.from(seg.segment(word), (s) => s.segment);
  }
  return [word];
}
export default function SplitText({
  text,
  className = "",
  baseDelay = 0,
  stagger = 18,
}: SplitTextProps) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            el.classList.add("in");
            io.disconnect();
          }
        }
      },
      { threshold: 0.2 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  let i = 0;
  const words = text.split(" ");
  return (
    <span ref={ref} className={`split ${className}`}>
      {words.map((w, wi) => (
        <Fragment key={wi}>
          <span className="split-word">
            {splitGraphemes(w).map((ch, ci) => {
              const style = { "--d": `${baseDelay + i++ * stagger}ms` } as CSSProperties;
              return (
                <span key={ci} className="split-char" style={style}>
                  {ch}
                </span>
              );
            })}
          </span>
          {wi < words.length - 1 ? " " : null}
        </Fragment>
      ))}
    </span>
  );
}
