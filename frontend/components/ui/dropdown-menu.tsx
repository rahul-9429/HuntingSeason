"use client";

import { DropdownMenu as MenuPrimitive } from "radix-ui";
import { cn } from "@/lib/utils";

export const DropdownMenu = MenuPrimitive.Root;
export const DropdownMenuTrigger = MenuPrimitive.Trigger;

export function DropdownMenuContent({
  className,
  align = "end",
  sideOffset = 6,
  ...props
}: React.ComponentProps<typeof MenuPrimitive.Content>) {
  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Content
        align={align}
        sideOffset={sideOffset}
        className={cn(
          "z-50 min-w-44 rounded-lg border-2 border-line-strong bg-surface p-1 shadow-pop outline-none data-[state=open]:animate-enter",
          className,
        )}
        {...props}
      />
    </MenuPrimitive.Portal>
  );
}

const itemClass =
  "relative flex h-8 cursor-default select-none items-center gap-2 rounded-md px-2 text-ui text-ink outline-none data-[disabled]:pointer-events-none data-[highlighted]:bg-sunken data-[disabled]:opacity-50 [&_svg]:size-3.5 [&_svg]:shrink-0 [&_svg]:text-ink-3";

export function DropdownMenuItem({
  className,
  ...props
}: React.ComponentProps<typeof MenuPrimitive.Item>) {
  return <MenuPrimitive.Item className={cn(itemClass, className)} {...props} />;
}

export function DropdownMenuSegmentedGroup({
  className,
  ...props
}: React.ComponentProps<typeof MenuPrimitive.RadioGroup>) {
  return (
    <MenuPrimitive.RadioGroup
      className={cn("inline-flex items-center gap-0.5 rounded-lg border bg-sunken/70 p-0.5", className)}
      {...props}
    />
  );
}

export function DropdownMenuSegmentedItem({
  className,
  ...props
}: React.ComponentProps<typeof MenuPrimitive.RadioItem>) {
  return (
    <MenuPrimitive.RadioItem
      className={cn(
        "grid size-6 cursor-default place-items-center rounded-md text-ink-3 outline-none transition focus-visible:ring-2 focus-visible:ring-accent-500/30 data-[highlighted]:text-ink data-[state=checked]:bg-surface data-[state=checked]:text-ink data-[state=checked]:data-[state=checked]:ring-1 data-[state=checked]:ring-line [&_svg]:size-3.5",
        className,
      )}
      {...props}
    />
  );
}

export function DropdownMenuLabel({
  className,
  ...props
}: React.ComponentProps<typeof MenuPrimitive.Label>) {
  return (
    <MenuPrimitive.Label
      className={cn("px-2 pb-1 pt-1.5 text-micro font-medium text-ink-3", className)}
      {...props}
    />
  );
}

export function DropdownMenuSeparator({
  className,
  ...props
}: React.ComponentProps<typeof MenuPrimitive.Separator>) {
  return <MenuPrimitive.Separator className={cn("-mx-1 my-1 h-px bg-line", className)} {...props} />;
}
