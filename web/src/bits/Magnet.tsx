import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { useEffect } from "react";
import type { ReactNode } from "react";

interface MagnetProps {
  children: ReactNode;
  strength?: number;
  className?: string;
}

/* Magnetic hover (React Bits "Magnet"). Pointer physics live in Motion
   values, outside the React render cycle. Collapses to static output
   under prefers-reduced-motion. */
export default function Magnet({ children, strength = 14, className = "" }: MagnetProps) {
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useTransform(x, (v) => v * strength);
  const sy = useTransform(y, (v) => v * strength);

  useEffect(() => {
    if (reduce) {
      x.set(0);
      y.set(0);
    }
  }, [reduce, x, y]);

  function onMove(e: React.MouseEvent<HTMLDivElement>) {
    if (reduce) return;
    const r = e.currentTarget.getBoundingClientRect();
    x.set((e.clientX - (r.left + r.width / 2)) / r.width);
    y.set((e.clientY - (r.top + r.height / 2)) / r.height);
  }

  function onLeave() {
    animate(x, 0, { type: "spring", stiffness: 180, damping: 16 });
    animate(y, 0, { type: "spring", stiffness: 180, damping: 16 });
  }

  return (
    <motion.div
      className={`magnet ${className}`}
      style={reduce ? undefined : { x: sx, y: sy }}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
    >
      {children}
    </motion.div>
  );
}
