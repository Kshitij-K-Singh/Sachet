import { useEffect, useState } from "react";
import CountUp from "../bits/CountUp";
import type { ReactElement } from "react";

export type MeterLevel = "low" | "medium" | "high";

interface MeterProps {
  value: number;
  max?: number;
  level: MeterLevel;
  label: string;
  /** Display text for the level and the Low/Medium/High scale. The `level`
      code still drives colour and fill; only these visible words translate. */
  levelText: string;
  scale: [string, string, string];
}

const LEVEL_COLOR: Record<MeterLevel, string> = {
  low: "#34d399",
  medium: "#fff600",
  high: "#fa003f",
};

/* Measurement on a fixed scale (PanelUI "Meter"), with an animated fill
   and counting score (Rare UI "Animated Counter"). */
export default function Meter({ value, max = 10, level, label, levelText, scale }: MeterProps): ReactElement {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const [w, setW] = useState(0);

  useEffect(() => {
    const id = requestAnimationFrame(() => setW(pct));
    return () => cancelAnimationFrame(id);
  }, [pct]);

  return (
    <div className="pmeter" role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max} aria-label={label}>
      <div className="pmeter-top">
        <span className="pmeter-level" style={{ color: LEVEL_COLOR[level] }}>
          <span className="pmeter-dot" />
          {label}: <strong>{levelText}</strong>
        </span>
        <span className="pmeter-score">
          <CountUp value={value} />
          <span className="pmeter-max">/{max}</span>
        </span>
      </div>
      <div className="pmeter-track">
        <div className={`pmeter-fill ${level}`} style={{ width: `${w}%` }} />
        <div className="pmeter-ticks" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </div>
      </div>
      <div className="pmeter-scale">
        <span>{scale[0]}</span>
        <span>{scale[1]}</span>
        <span>{scale[2]}</span>
      </div>
    </div>
  );
}
