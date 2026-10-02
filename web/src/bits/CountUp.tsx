import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { useEffect } from "react";

interface CountUpProps {
  value: number;
  duration?: number;
  className?: string;
}

/* Animated counter (Rare UI "Animated Counter"). Counting runs on a Motion
   value, so frames never re-render the tree. Instant under reduced motion. */
export default function CountUp({ value, duration = 0.9, className = "" }: CountUpProps) {
  const reduce = useReducedMotion();
  const mv = useMotionValue(0);
  const rounded = useTransform(mv, (v) => Math.round(v));

  useEffect(() => {
    if (reduce) {
      mv.set(value);
      return;
    }
    mv.set(0);
    const controls = animate(mv, value, {
      duration,
      ease: [0.16, 1, 0.3, 1],
    });
    return () => controls.stop();
  }, [value, duration, mv, reduce]);

  return <motion.span className={className}>{rounded}</motion.span>;
}
