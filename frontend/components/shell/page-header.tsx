import { cn } from "@/lib/utils";

interface PageHeaderProps {
  eyebrow: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({ eyebrow, title, description, actions, className }: PageHeaderProps) {
  return (
    <header
      className={cn(
        "mb-7 flex flex-wrap items-end justify-between gap-x-8 gap-y-4 border-b-2 border-line-strong pb-5",
        className,
      )}
    >
      <div className="min-w-0 max-w-2xl">
        <p className="flex items-center gap-2 font-mono text-micro font-semibold uppercase tracking-[0.18em] text-accent-700">
          <span aria-hidden className="h-3.5 w-1 bg-accent-500" />
          {eyebrow}
        </p>
        <h1 className="mt-3 text-[34px] font-bold leading-[1.02] tracking-[-0.03em] text-ink sm:text-[42px]">
          {title}
        </h1>
        {description && (
          <p className="mt-3 max-w-xl text-ui leading-relaxed text-ink-2">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
