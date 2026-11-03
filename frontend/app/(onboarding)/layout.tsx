import { Suspense } from "react";
import { AppProviders, RequireAuth } from "@/components/providers/app-providers";

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppProviders>
      <main className="scrollbar-thin h-dvh overflow-y-auto">
        <Suspense fallback={<div aria-hidden className="mx-auto mt-24 h-64 max-w-2xl animate-pulse rounded-xl bg-sunken/70" />}>
          <RequireAuth>{children}</RequireAuth>
        </Suspense>
      </main>
    </AppProviders>
  );
}
