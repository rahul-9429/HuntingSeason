import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

export const badgeVariants = cva(
  "inline-flex items-center gap-1 whitespace-nowrap rounded-[2px] border px-1.5 py-px font-mono text-micro font-semibold uppercase tracking-[0.08em] [&_svg]:size-3 [&_svg]:shrink-0",
  {
    variants: {
      tone: {
        neutral: "border-line-strong bg-sunken text-ink-2",
        outline: "border-line-strong bg-transparent text-ink-2",
        accent: "border-accent-400 bg-accent-100 text-accent-800",
        amber:
          "border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-400/40 dark:bg-amber-400/15 dark:text-amber-200",
        sky: "border-sky-300 bg-sky-100 text-sky-800 dark:border-sky-400/40 dark:bg-sky-400/15 dark:text-sky-200",
        rose: "border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-400/40 dark:bg-rose-400/15 dark:text-rose-200",
        ink: "border-ink bg-ink text-on-ink",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps
  extends React.ComponentProps<"span">,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
