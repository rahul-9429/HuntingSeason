import { type QueryClient, useIsMutating, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { queryKeys } from "@/lib/queries/keys";
import type { CareerProfile, ExperienceTimeline, Preferences, Resume, UserProfile } from "@/lib/types";

const PARSE_POLL_MS = 1500;
const uploadResumeKey = ["resume", "upload"];

export function useProfile() {
  return useQuery({
    queryKey: queryKeys.profile,
    queryFn: async () => (await api.get<UserProfile>("/v1/profile")).data,
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (patch: Partial<UserProfile>) => (await api.patch<UserProfile>("/v1/profile", patch)).data,
    onSuccess: (profile) => queryClient.setQueryData(queryKeys.profile, profile),
  });
}

export function useExperience() {
  return useQuery({
    queryKey: queryKeys.experience,
    queryFn: async () => (await api.get<ExperienceTimeline>("/v1/profile/experience")).data,
  });
}

export function usePreferences() {
  return useQuery({
    queryKey: queryKeys.preferences,
    queryFn: async () => (await api.get<Preferences>("/v1/preferences")).data,
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (patch: Partial<Preferences>) => (await api.patch<Preferences>("/v1/preferences", patch)).data,
    onSuccess: (preferences) => queryClient.setQueryData(queryKeys.preferences, preferences),
  });
}

export function useResume() {
  const uploading = useIsMutating({ mutationKey: uploadResumeKey }) > 0;
  return useQuery({
    queryKey: queryKeys.resume,
    queryFn: async () => (await api.get<Resume | null>("/v1/resumes/latest")).data,
    refetchInterval: (query) => (!uploading && query.state.data?.status === "parsing" ? PARSE_POLL_MS : false),
  });
}

export function useUploadResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: uploadResumeKey,
    mutationFn: async ({ file, onProgress }: { file: File; onProgress: (percent: number) => void }) => {
      const form = new FormData();
      form.append("file", file);
      let { data: resume } = await api.post<Resume>("/v1/resumes", form, {
        onUploadProgress: (event) => onProgress(Math.round((event.progress ?? 0) * 100)),
      });
      while (resume.status === "parsing") {
        queryClient.setQueryData(queryKeys.resume, resume);
        await new Promise((resolve) => setTimeout(resolve, PARSE_POLL_MS));
        resume = (await api.get<Resume>(`/v1/resumes/${resume.id}`)).data;
      }
      return resume;
    },
    onSuccess: (resume) => {
      queryClient.setQueryData(queryKeys.resume, resume);
      void queryClient.invalidateQueries({ queryKey: queryKeys.contacts });
      if (resume.status === "parsed") profileChanged(queryClient, resume.profile);
    },
  });
}

export function useCareerProfile() {
  return useQuery({
    queryKey: queryKeys.careerProfile,
    queryFn: async () => (await api.get<CareerProfile | null>("/v1/career-profile")).data,
  });
}

export function useUpdateCareerProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (profile: CareerProfile) => (await api.put<CareerProfile>("/v1/career-profile", profile)).data,
    onSuccess: (profile) => {
      queryClient.setQueryData(queryKeys.careerProfile, profile);
      queryClient.removeQueries({ queryKey: queryKeys.companySearches });
    },
  });
}

/** Résumé-shaped searches are stale once the profile behind them changes. */
function profileChanged(queryClient: QueryClient, parsed: CareerProfile | null) {
  // The parse just saved this as the profile; show it now rather than after a refetch
  if (parsed) queryClient.setQueryData(queryKeys.careerProfile, parsed);
  void queryClient.invalidateQueries({ queryKey: queryKeys.careerProfile });
  void queryClient.invalidateQueries({ queryKey: queryKeys.profile });
  void queryClient.invalidateQueries({ queryKey: queryKeys.preferences });
  queryClient.removeQueries({ queryKey: queryKeys.companySearches });
}
