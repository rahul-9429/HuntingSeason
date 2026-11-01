"use client";

import { Switch as SwitchPrimitive } from "radix-ui";
import { cn } from "@/lib/utils";

export function Switch({ className, ...props }: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        "inline-flex h-[18px] w-8 shrink-0 cursor-pointer items-center rounded-full border border-transparent bg-line-strong outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent-500/30 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-accent-600",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="pointer-events-none block size-3.5 rounded-full bg-white shadow-raised transition-transform duration-150 data-[state=checked]:translate-x-[15px] data-[state=unchecked]:translate-x-px" />
    </SwitchPrimitive.Root>
  );
}
