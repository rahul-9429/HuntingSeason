function BrandMark() {
  return (
    <span className="flex items-center gap-2.5">
      <span
        aria-hidden
        className="grid size-6 place-items-center rounded-md bg-ink pb-px font-serif text-[17px] italic leading-none text-on-ink"
      >
        j
      </span>
      <span className="text-[15px] font-semibold tracking-tight text-ink">Hunting Season</span>
    </span>
  );
}

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <aside className="hidden flex-col border-r bg-sunken/60 px-12 py-10 lg:flex">
        <BrandMark />
        <h1 className="my-auto max-w-md font-serif text-[46px] leading-[1.02] tracking-[-0.01em] text-ink">
          The right people, <em className="text-accent-700">before the job post.</em>
        </h1>
      </aside>

      <main className="flex flex-col items-center justify-center bg-canvas px-5 py-12">
        <div className="mb-8 lg:hidden">
          <BrandMark />
        </div>
        {children}
      </main>
    </div>
  );
}
