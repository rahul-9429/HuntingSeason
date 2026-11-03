import { auth } from "@clerk/nextjs/server";
import { QueryProvider } from "@/components/providers/query-provider";
import { StoreProvider } from "@/components/providers/store-provider";
import { ToastProvider } from "@/components/ui/toast";
import { TooltipProvider } from "@/components/ui/tooltip";

/** Everything a signed-in page needs: store, toasts, API session + queries, tooltips. */
export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <StoreProvider>
      <ToastProvider>
        <QueryProvider>
          <TooltipProvider delayDuration={300}>{children}</TooltipProvider>
        </QueryProvider>
      </ToastProvider>
    </StoreProvider>
  );
}

export async function RequireAuth({ children }: { children: React.ReactNode }) {
  await auth.protect();
  return <>{children}</>;
}
