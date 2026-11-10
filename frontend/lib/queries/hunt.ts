import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { queryKeys } from "@/lib/queries/keys";
import type { HuntSettings } from "@/lib/types";

export function useHuntSettings() {
  return useQuery({
    queryKey: queryKeys.huntSettings,
    queryFn: async () => (await api.get<HuntSettings>("/v1/hunt/settings")).data,
  });
}

export type HuntSettingsChanges = Partial<Pick<HuntSettings, "enabled" | "run_credit_budget">>;

export function useUpdateHuntSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (changes: HuntSettingsChanges) =>
      (await api.put<HuntSettings>("/v1/hunt/settings", changes)).data,
    onMutate: async (changes) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.huntSettings });
      const previous = queryClient.getQueryData<HuntSettings>(queryKeys.huntSettings);
      if (previous) queryClient.setQueryData(queryKeys.huntSettings, { ...previous, ...changes });
      return { previous };
    },
    onError: (_error, _changes, context) =>
      queryClient.setQueryData(queryKeys.huntSettings, context?.previous),
    onSuccess: (settings) => queryClient.setQueryData(queryKeys.huntSettings, settings),
  });
}

export function useRunHunt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => (await api.post<{ queued: boolean }>("/v1/hunt/run")).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.huntSettings });
      void queryClient.invalidateQueries({ queryKey: queryKeys.outreachCompanies });
      void queryClient.invalidateQueries({ queryKey: queryKeys.contacts });
      void queryClient.invalidateQueries({ queryKey: queryKeys.credits });
    },
  });
}
