"use client";

import { X } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { cn } from "@/lib/utils";

export const Sheet = DialogPrimitive.Root;
export const SheetClose = DialogPrimitive.Close;

export function SheetContent({
  className,
  children,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content>) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-scrim data-[state=open]:animate-overlay" />
      <DialogPrimitive.Content
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-[540px] flex-col border-l bg-surface shadow-pop outline-none data-[state=open]:animate-sheet",
          className,
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close className="absolute right-4 top-4 grid size-7 place-items-center rounded-md text-ink-3 outline-none transition hover:bg-sunken hover:text-ink focus-visible:ring-2 focus-visible:ring-accent-500/30">
          <X className="size-4" />
          <span className="sr-only">Close</span>
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function SheetHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("border-b px-6 py-5 pr-14", className)} {...props} />;
}

export function SheetTitle({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      className={cn("text-[15px] font-semibold tracking-tight text-ink", className)}
      {...props}
    />
  );
}

export function SheetDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description className={cn("mt-1 text-ui text-ink-2", className)} {...props} />
  );
}

export function SheetFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex flex-wrap items-center justify-between gap-3 border-t bg-canvas/60 px-6 py-4", className)}
      {...props}
    />
  );
}
