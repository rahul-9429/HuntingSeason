"use client";

import { Check, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SettingsCardProps {
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

export function SettingsCard({ title, description, action, footer, className, children }: SettingsCardProps) {
  return (
    <section className={cn("rounded-xl border-2 border-line-strong bg-surface", className)}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b px-6 py-4">
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h2>
          {description && <p className="mt-0.5 max-w-xl text-ui text-ink-2">{description}</p>}
        </div>
        {action}
      </header>
      <div className="px-6 py-5">{children}</div>
      {footer && (
        <footer className="flex items-center justify-end gap-3 rounded-b-xl border-t bg-canvas/60 px-6 py-3">
          {footer}
        </footer>
      )}
    </section>
  );
}

export function SaveBar({ dirty, saving = false, onSave }: { dirty: boolean; saving?: boolean; onSave: () => void }) {
  return (
    <>
      <span
        className={cn(
          "mr-auto flex items-center gap-1.5 text-micro",
          dirty ? "text-amber-700 dark:text-amber-400" : "text-ink-3",
        )}
      >
        {dirty ? (
          "Unsaved changes"
        ) : (
          <>
            <Check className="size-3 text-accent-700" /> All changes saved
          </>
        )}
      </span>
      <Button variant="primary" size="sm" disabled={!dirty || saving} onClick={onSave}>
        {saving && <LoaderCircle className="animate-spin" />}
        {saving ? "Saving…" : "Save changes"}
      </Button>
    </>
  );
}

export function SettingsCardSkeleton() {
  return (
    <div aria-hidden className="animate-pulse rounded-xl border-2 border-line-strong bg-surface">
      <div className="space-y-2 border-b px-6 py-4">
        <div className="h-4 w-40 rounded bg-sunken" />
        <div className="h-3 w-72 max-w-full rounded bg-sunken" />
      </div>
      <div className="space-y-4 px-6 py-5">
        <div className="h-8 rounded-md bg-sunken" />
        <div className="h-8 rounded-md bg-sunken" />
        <div className="h-8 w-2/3 rounded-md bg-sunken" />
      </div>
    </div>
  );
}

export function SettingRow({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-3.5 first:pt-0 last:pb-0">
      <div className="min-w-0 max-w-md">
        <p className="text-ui font-medium text-ink">{label}</p>
        {description && <p className="mt-0.5 text-micro text-ink-3">{description}</p>}
      </div>
      {children}
    </div>
  );
}
