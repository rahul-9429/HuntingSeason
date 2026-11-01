export function AuthFormSkeleton() {
  return (
    <div aria-hidden className="w-full max-w-[400px] animate-pulse rounded-xl border-2 border-line-strong bg-surface p-8 shadow-raised">
      <div className="mx-auto h-5 w-40 rounded bg-sunken" />
      <div className="mx-auto mt-2 h-3 w-56 rounded bg-sunken" />
      <div className="mt-8 h-9 rounded-md bg-sunken" />
      <div className="mt-6 h-3 w-16 rounded bg-sunken" />
      <div className="mt-2 h-9 rounded-md bg-sunken" />
      <div className="mt-6 h-9 rounded-md bg-ink/15" />
    </div>
  );
}
