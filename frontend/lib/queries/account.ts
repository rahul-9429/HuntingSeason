import { useAuth } from "@clerk/nextjs";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { queryKeys } from "@/lib/queries/keys";
import type { Credits, CurrentUser } from "@/lib/types";

export function useCurrentUser() {
  const { isSignedIn } = useAuth();
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: async () => (await api.get<CurrentUser>("/user/me")).data,
    enabled: isSignedIn === true,
  });
}

export function useCredits() {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: queryKeys.credits,
    queryFn: async () => {
      const credits = (await api.get<Credits>("/v1/credits")).data;
      queryClient.setQueryData(queryKeys.apolloCreditsLeft, credits.total - credits.used);
      return credits;
    },
  });
}
