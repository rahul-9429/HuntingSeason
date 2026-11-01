import { Suspense } from "react";
import { AppProviders, RequireAuth } from "@/components/providers/app-providers";
import { MobileNav, Sidebar } from "@/components/shell/sidebar";

function PageSkeleton() {
  return (
    <div aria-hidden className="h-full animate-pulse px-5 py-10 sm:px-8 lg:px-10">
      <div className="h-3 w-28 rounded bg-sunken" />
      <div className="mt-4 h-9 w-80 max-w-full rounded bg-sunken" />
      <div className="mt-8 h-40 rounded-xl bg-sunken/70" />
    </div>
  );
}

function SidebarSkeleton() {
  return <div aria-hidden className="hidden w-[248px] shrink-0 border-r bg-canvas md:block" />;
}

function MobileNavSkeleton() {
  return <div aria-hidden className="h-12 shrink-0 border-b bg-canvas md:hidden" />;
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppProviders>
      <div className="flex h-dvh flex-col md:flex-row">
        <Suspense fallback={<SidebarSkeleton />}>
          <Sidebar />
        </Suspense>
        <Suspense fallback={<MobileNavSkeleton />}>
          <MobileNav />
        </Suspense>
        <main className="relative min-h-0 min-w-0 flex-1">
          <Suspense fallback={<PageSkeleton />}>
            <RequireAuth>{children}</RequireAuth>
          </Suspense>
        </main>
      </div>
    </AppProviders>
  );
}
