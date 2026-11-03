import { skipToken, useInfiniteQuery, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { queryKeys } from "@/lib/queries/keys";
import type { CompanyFilters, CompanySearchPage, Credits, JobPostings } from "@/lib/types";

const noRefetch = {
  staleTime: Infinity,
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
  retry: false,
} as const;

export function setCreditsLeft(queryClient: QueryClient, left: number) {
  queryClient.setQueryData(queryKeys.apolloCreditsLeft, left);
  queryClient.setQueryData<Credits>(queryKeys.credits, (credits) =>
    credits ? { ...credits, used: credits.total - left } : credits,
  );
}

interface SearchPageParam {
  page: number;
  filters: CompanyFilters | null;
}

/** A submitted search; `null` until the user searches. */
export interface CompanySearchInput {
  query: string;
  useProfile: boolean;
}

export function useCompanySearch(search: CompanySearchInput | null) {
  const queryClient = useQueryClient();
  const query = search?.query ?? "";
  const useProfile = search?.useProfile ?? false;
  return useInfiniteQuery({
    queryKey: queryKeys.companySearch(query, useProfile),
    queryFn: async ({ pageParam }) => {
      const page = (
        await api.post<CompanySearchPage>("/v1/companies/search", { query, use_profile: useProfile, ...pageParam })
      ).data;
      setCreditsLeft(queryClient, page.credits_left);
      return page;
    },
    initialPageParam: { page: 1, filters: null } as SearchPageParam,
    getNextPageParam: (last): SearchPageParam | undefined =>
      last.has_more ? { page: last.page + 1, filters: last.filters } : undefined,
    enabled: search !== null,
    ...noRefetch,
  });
}

export function useJobPostings(orgId: string, roles: string[]) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: queryKeys.jobPostings(orgId, roles),
    queryFn: async () => {
      const postings = (
        await api.get<JobPostings>(`/v1/companies/${orgId}/job-postings`, {
          params: new URLSearchParams(roles.map((role) => ["role", role])),
        })
      ).data;
      setCreditsLeft(queryClient, postings.credits_left);
      return postings;
    },
    ...noRefetch,
  });
}

export function useApolloCreditsLeft() {
  return useQuery<number>({ queryKey: queryKeys.apolloCreditsLeft, queryFn: skipToken, staleTime: Infinity }).data;
}
