import { Fragment, useEffect, useRef } from "react";
import type { CSSProperties } from "react";

interface SplitTextProps {
  text: string;
  className?: string;
  baseDelay?: number;
  stagger?: number;
}

/* Staggered character reveal (React Bits "SplitText"). */
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
            {w.split("").map((ch, ci) => {
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
