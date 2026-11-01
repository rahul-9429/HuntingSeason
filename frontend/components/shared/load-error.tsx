import { CloudOff, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface LoadErrorProps {
  what: string;
  detail?: string;
  onRetry: () => void;
  className?: string;
}

export function LoadError({ what, detail, onRetry, className }: LoadErrorProps) {
  return (
    <div role="alert" className={cn("rounded-xl border border-dashed bg-surface/60 px-6 py-12 text-center", className)}>
      <CloudOff className="mx-auto size-5 text-ink-3" />
      <p className="mt-2 text-ui font-medium text-ink">Couldn’t load {what}</p>
      {detail && <p className="mx-auto mt-1 max-w-md text-micro text-ink-2">{detail}</p>}
      <Button size="sm" onClick={onRetry} className="mt-3">
        <RotateCw /> Try again
      </Button>
    </div>
  );
}
