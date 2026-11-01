import { hueClasses } from "@/lib/labels";
import type { Hue } from "@/lib/types";
import { cn, hueFor, initials } from "@/lib/utils";

const sizes = {
  xs: "size-5 text-[9px]",
  sm: "size-7 text-[10.5px]",
  md: "size-8 text-[11px]",
  lg: "size-10 text-ui",
  xl: "size-14 text-base",
} as const;

interface AvatarProps {
  name: string;
  size?: keyof typeof sizes;
  hue?: Hue | "ink";
  className?: string;
}

export function Avatar({ name, size = "md", hue, className }: AvatarProps) {
  const tone = hue === "ink" ? "bg-ink text-on-ink" : hueClasses[hue ?? hueFor(name)];
  return (
    <span
      aria-hidden
      className={cn(
        "inline-grid shrink-0 select-none place-items-center rounded-full font-semibold tracking-tight",
        sizes[size],
        tone,
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}

const markSizes = {
  xs: "size-4 rounded-[4px] text-[9px]",
  sm: "size-5 rounded-[5px] text-[10px]",
  md: "size-7 rounded-md text-xs",
  lg: "size-9 rounded-lg text-sm",
} as const;

export function CompanyMark({
  name,
  hue,
  size = "sm",
  className,
}: {
  name: string;
  hue: Hue;
  size?: keyof typeof markSizes;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-grid shrink-0 place-items-center font-semibold",
        markSizes[size],
        hueClasses[hue],
        className,
      )}
    >
      {name[0]}
    </span>
  );
}
