import { cn } from "@/lib/utils";

export function LiveDot({ live, className }: { live: boolean; className?: string }) {
  return (
    <span className={cn("relative flex size-2 shrink-0", className)} aria-hidden>
      {live && (
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-accent-400 opacity-50 [animation-duration:2s]" />
      )}
      <span className={cn("relative inline-flex size-2 rounded-full", live ? "bg-accent-500" : "bg-ink-3")} />
    </span>
  );
}
