import { cn } from "@/lib/utils";

const controlClass =
  "w-full rounded-[2px] border-2 border-line-strong bg-surface text-ui text-ink outline-none transition-colors placeholder:text-ink-3 hover:border-accent-500 focus:border-accent-500 focus:ring-2 focus:ring-accent-500/25 disabled:cursor-not-allowed disabled:opacity-50";

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return <input className={cn(controlClass, "h-9 px-3", className)} {...props} />;
}

export function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return <textarea className={cn(controlClass, "resize-none px-3 py-2 leading-5", className)} {...props} />;
}

export function Select({ className, ...props }: React.ComponentProps<"select">) {
  return <select className={cn(controlClass, "h-9 cursor-pointer px-2.5", className)} {...props} />;
}

export function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      className={cn(
        "font-mono text-micro font-semibold uppercase tracking-[0.12em] text-ink-2",
        className,
      )}
      {...props}
    />
  );
}

export function Field({
  label,
  hint,
  htmlFor,
  className,
  children,
}: {
  label: string;
  hint?: string;
  htmlFor?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-micro text-ink-3">{hint}</p>}
    </div>
  );
}
