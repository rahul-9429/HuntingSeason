export function InboxSkeleton() {
  return (
    <div className="flex h-full animate-pulse" aria-hidden>
      <div className="w-full space-y-4 border-r bg-surface p-4 md:w-[340px] lg:w-[372px]">
        <div className="h-7 w-24 rounded bg-sunken" />
        <div className="h-8 rounded-md bg-sunken" />
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="flex gap-3 py-2">
            <div className="size-7 rounded-full bg-sunken" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-2/3 rounded bg-sunken" />
              <div className="h-3 w-full rounded bg-sunken" />
            </div>
          </div>
        ))}
      </div>
      <div className="hidden flex-1 bg-surface md:block" />
    </div>
  );
}

export function ThreadDetailSkeleton() {
  return (
    <div aria-hidden className="flex h-full animate-pulse flex-col bg-surface">
      <div className="space-y-3 border-b px-5 pb-3 pt-4 lg:px-6">
        <div className="h-3 w-16 rounded bg-sunken" />
        <div className="h-5 w-2/3 rounded bg-sunken" />
        <div className="h-7 w-48 rounded bg-sunken" />
      </div>
      <div className="mx-auto w-full max-w-2xl space-y-4 px-5 py-6">
        <div className="h-32 rounded-xl bg-sunken/70" />
        <div className="h-24 rounded-xl bg-sunken/70" />
      </div>
    </div>
  );
}
