"use client";

import { ToggleGroup } from "radix-ui";
import { cn } from "@/lib/utils";

export interface SegmentedOption<T extends string> {
  value: T;
  label: React.ReactNode;
  count?: number;
  disabled?: boolean;
}

interface SegmentedProps<T extends string> {
  value: T;
  onValueChange: (value: T) => void;
  options: SegmentedOption<T>[];
  "aria-label": string;
  className?: string;
}

export function Segmented<T extends string>({
  value,
  onValueChange,
  options,
  className,
  ...props
}: SegmentedProps<T>) {
  return (
    <ToggleGroup.Root
      type="single"
      value={value}
      onValueChange={(next) => next && onValueChange(next as T)}
      aria-label={props["aria-label"]}
      className={cn(
        "inline-flex items-center gap-0 rounded-[2px] border-2 border-line-strong bg-surface p-0",
        className,
      )}
    >
      {options.map((option) => (
        <ToggleGroup.Item
          key={option.value}
          value={option.value}
          disabled={option.disabled}
          className="inline-flex h-8 cursor-pointer items-center gap-1.5 whitespace-nowrap border-r-2 border-line-strong px-3 font-mono text-micro font-semibold uppercase tracking-[0.08em] text-ink-2 outline-none transition-colors last:border-r-0 hover:bg-sunken hover:text-ink focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-500/40 disabled:cursor-not-allowed disabled:opacity-40 data-[state=on]:bg-accent-200 data-[state=on]:font-bold data-[state=on]:text-ink"
        >
          {option.label}
          {option.count !== undefined && (
            <span className="tabular-nums opacity-60">{option.count}</span>
          )}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}

export function Chip({
  pressed,
  onPressedChange,
  children,
  className,
}: {
  pressed: boolean;
  onPressedChange: (pressed: boolean) => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={() => onPressedChange(!pressed)}
      className={cn(
        "inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-[2px] border-2 px-3 font-mono text-micro font-semibold uppercase tracking-[0.08em] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent-500/40 [&_svg]:size-3.5",
        pressed
          ? "border-accent-500 bg-accent-200 text-accent-900"
          : "border-line-strong bg-surface text-ink-2 hover:border-accent-500 hover:text-ink",
        className,
      )}
    >
      {children}
    </button>
  );
}
