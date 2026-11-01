import { cn } from "@/lib/utils";

const RADIUS = 15;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function scoreColor(value: number) {
  if (value >= 85) return "text-accent-700";
  if (value >= 75) return "text-accent-600";
  return "text-amber-600";
}

export function ScoreRing({ value, className }: { value: number; className?: string }) {
  return (
    <span
      role="img"
      aria-label={`${value}% match`}
      className={cn("relative inline-grid size-11 shrink-0 place-items-center", className)}
    >
      <svg viewBox="0 0 36 36" className="absolute inset-0 -rotate-90" aria-hidden>
        <circle cx="18" cy="18" r={RADIUS} fill="none" strokeWidth="3" className="stroke-line" />
        <circle
          cx="18"
          cy="18"
          r={RADIUS}
          fill="none"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - value / 100)}
          className={cn("stroke-current", scoreColor(value))}
        />
      </svg>
      <span className="font-mono text-[12px] font-medium tabular-nums text-ink">{value}</span>
    </span>
  );
}
