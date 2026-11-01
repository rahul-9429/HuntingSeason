import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex shrink-0 cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-[2px] text-ui font-semibold outline-none transition-all duration-100 focus-visible:ring-2 focus-visible:ring-accent-500/40 focus-visible:ring-offset-1 focus-visible:ring-offset-canvas disabled:pointer-events-none disabled:opacity-40 [&_svg]:size-3.5 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary:
          "border-2 border-ink bg-ink text-on-ink shadow-[2px_2px_0_0_var(--color-line-strong)] hover:-translate-y-px hover:shadow-[3px_3px_0_0_var(--color-line-strong)] active:translate-y-0 active:shadow-none",
        accent:
          "border-2 border-accent-600 bg-accent-300 text-ink shadow-[2px_2px_0_0_var(--color-accent-500)] hover:-translate-y-px hover:bg-accent-200 hover:shadow-[3px_3px_0_0_var(--color-accent-500)] active:translate-y-0 active:shadow-none",
        secondary:
          "border-2 border-line-strong bg-surface text-ink hover:border-accent-500 hover:bg-accent-50",
        ghost: "border-2 border-transparent text-ink-2 hover:bg-sunken hover:text-ink",
        subtle: "border-2 border-transparent bg-sunken text-ink hover:border-line-strong",
      },
      size: {
        sm: "h-8 px-3",
        md: "h-9 px-3.5",
        lg: "h-10 px-5 text-[0.875rem]",
        icon: "size-9",
        "icon-sm": "size-8",
      },
    },
    defaultVariants: {
      variant: "secondary",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends React.ComponentProps<"button">,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({ className, variant, size, asChild = false, type, ...props }: ButtonProps) {
  const Comp = asChild ? Slot.Root : "button";
  return (
    <Comp
      data-slot="button"
      type={asChild ? undefined : (type ?? "button")}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}
