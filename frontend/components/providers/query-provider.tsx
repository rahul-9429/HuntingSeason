"use client";

import { useAuth } from "@clerk/nextjs";
import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useToast } from "@/components/ui/toast";
import { JWT_TEMPLATE, errorMessage, setTokenGetter } from "@/lib/api/client";
import { useCurrentUser } from "@/lib/queries/account";

function ApiSession() {
  const { getToken } = useAuth();

  useEffect(() => {
    setTokenGetter(() => getToken({ template: JWT_TEMPLATE }));
  }, [getToken]);

  // The backend creates the user's row (or links it by email) on their first call after signing in.
  useCurrentUser();
  return null;
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const toast = useToast();
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
        mutationCache: new MutationCache({
          onError: (error) => toast({ title: errorMessage(error) }),
        }),
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ApiSession />
      {children}
    </QueryClientProvider>
  );
}
