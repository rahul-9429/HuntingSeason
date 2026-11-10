"use client";

import { cn } from "@/lib/utils";

interface SliderProps {
  value: number;
  min?: number;
  max: number;
  step?: number;
  disabled?: boolean;
  onValueChange: (value: number) => void;
  onCommit?: (value: number) => void;
  "aria-label": string;
  valueText?: string;
  className?: string;
}

export function Slider({
  value,
  min = 0,
  max,
  step = 1,
  disabled = false,
  onValueChange,
  onCommit,
  valueText,
  className,
  ...props
}: SliderProps) {
  const filled = max > min ? ((value - min) / (max - min)) * 100 : 0;

  return (
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      disabled={disabled}
      aria-label={props["aria-label"]}
      aria-valuetext={valueText}
      onChange={(event) => onValueChange(Number(event.target.value))}
      onPointerUp={() => onCommit?.(value)}
      onBlur={() => onCommit?.(value)}
      style={{ "--filled": `${filled}%` } as React.CSSProperties}
      className={cn(
        "h-1.5 w-full cursor-pointer appearance-none rounded-full bg-sunken outline-none",
        "bg-[linear-gradient(to_right,var(--color-accent-500)_0_var(--filled),transparent_var(--filled))]",
        "focus-visible:ring-2 focus-visible:ring-accent-500/40",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "[&::-webkit-slider-thumb]:size-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full",
        "[&::-webkit-slider-thumb]:border [&::-webkit-slider-thumb]:border-line-strong [&::-webkit-slider-thumb]:bg-surface",
        "[&::-webkit-slider-thumb]:[&::-webkit-slider-thumb]:transition",
        "[&::-moz-range-thumb]:size-4 [&::-moz-range-thumb]:appearance-none [&::-moz-range-thumb]:rounded-full",
        "[&::-moz-range-thumb]:border [&::-moz-range-thumb]:border-line-strong [&::-moz-range-thumb]:bg-surface",
        "[&::-moz-range-progress]:h-1.5 [&::-moz-range-progress]:rounded-full [&::-moz-range-progress]:bg-accent-500",
        className,
      )}
    />
  );
}
