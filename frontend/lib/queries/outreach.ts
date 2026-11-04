import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { queryKeys } from "@/lib/queries/keys";
import type {
  EmailSendSchedule,
  EmailTemplate,
  OutreachCompany,
  OutreachPreview,
  OutreachSettings,
  Writer,
} from "@/lib/types";

const POLL_MS = 2000;

export function useOutreachCompanies() {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: queryKeys.outreachCompanies,
    queryFn: async () => {
      const previous = queryClient.getQueryData<OutreachCompany[]>(queryKeys.outreachCompanies) ?? [];
      const companies = (await api.get<OutreachCompany[]>("/v1/outreach/companies")).data;
      const wasSearching = new Set(previous.filter((c) => c.status === "searching").map((c) => c.apollo_org_id));
      if (companies.some((c) => wasSearching.has(c.apollo_org_id) && c.status !== "searching")) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.contacts });
        void queryClient.invalidateQueries({ queryKey: queryKeys.credits });
      }
      return companies;
    },
    refetchInterval: (query) => (query.state.data?.some((c) => c.status === "searching") ? POLL_MS : false),
  });
}

export interface AddToOutreachInput {
  apolloOrgId: string;
  roles: string[];
  locations: string[];
}

export function useAddToOutreach() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ apolloOrgId, roles, locations }: AddToOutreachInput) =>
      (
        await api.post<OutreachCompany>("/v1/outreach/companies", {
          apollo_org_id: apolloOrgId,
          roles,
          locations,
        })
      ).data,
    onSuccess: async (company) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.outreachCompanies });
      queryClient.setQueryData<OutreachCompany[]>(queryKeys.outreachCompanies, (list = []) => [
        company,
        ...list.filter((c) => c.apollo_org_id !== company.apollo_org_id),
      ]);
    },
  });
}

export function useOutreachSettings() {
  return useQuery({
    queryKey: queryKeys.outreachSettings,
    queryFn: async () => (await api.get<OutreachSettings>("/v1/outreach/settings")).data,
  });
}

export type OutreachSettingsChanges = Partial<
  Omit<OutreachSettings, "updated_at" | "has_default_template" | "has_profile" | "blocker">
>;

export function useUpdateOutreachSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (changes: OutreachSettingsChanges) =>
      (await api.put<OutreachSettings>("/v1/outreach/settings", changes)).data,
    onMutate: async (changes) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.outreachSettings });
      const previous = queryClient.getQueryData<OutreachSettings>(queryKeys.outreachSettings);
      if (previous) queryClient.setQueryData(queryKeys.outreachSettings, { ...previous, ...changes });
      return { previous };
    },
    onError: (_error, _changes, context) =>
      queryClient.setQueryData(queryKeys.outreachSettings, context?.previous),
    onSuccess: (settings) => {
      queryClient.setQueryData(queryKeys.outreachSettings, settings);
      void queryClient.invalidateQueries({ queryKey: queryKeys.outreachPreviews, refetchType: "none" });
    },
  });
}

const SEND_SCHEDULE_URL = "/v1/outreach/settings/email-send-schedule";

export function useEmailSendSchedule() {
  return useQuery({
    queryKey: queryKeys.emailSendSchedule,
    queryFn: async () => (await api.get<EmailSendSchedule>(SEND_SCHEDULE_URL)).data,
  });
}

export interface EmailSendScheduleChanges {
  enabled?: boolean;
  country?: string;
  days?: number[];
}

export function useUpdateEmailSendSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (changes: EmailSendScheduleChanges) =>
      (await api.patch<EmailSendSchedule>(SEND_SCHEDULE_URL, changes)).data,
    onSuccess: (schedule) => {
      queryClient.setQueryData(queryKeys.emailSendSchedule, schedule);
      void queryClient.invalidateQueries({ queryKey: queryKeys.emailSendSchedule });
    },
  });
}

export function useRunOutreach() {
  return useMutation({
    mutationFn: async () => (await api.post<{ queued: boolean }>("/v1/outreach/run")).data,
  });
}

export function useOutreachPreview(contactId: string | null, options: { writer?: Writer; templateId?: number } = {}) {
  const { writer, templateId } = options;
  return useQuery({
    queryKey: queryKeys.outreachPreview(contactId ?? "", writer, templateId),
    queryFn: async () =>
      (
        await api.post<OutreachPreview>("/v1/outreach/preview", {
          contact_id: Number(contactId),
          writer,
          template_id: templateId,
        })
      ).data,
    enabled: contactId !== null,
    staleTime: Infinity,
    retry: false,
  });
}

export function useTemplates() {
  return useQuery({
    queryKey: queryKeys.templates,
    queryFn: async () => (await api.get<EmailTemplate[]>("/templates")).data,
  });
}

export type TemplateInput = Pick<EmailTemplate, "name" | "subject" | "body_html" | "skip_ai" | "is_default">;

function templatesChanged(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.templates });
  void queryClient.invalidateQueries({ queryKey: queryKeys.outreachPreviews, refetchType: "none" });
}

export function useSaveTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...template }: Partial<TemplateInput> & { id?: number }) =>
      (id === undefined
        ? await api.post<EmailTemplate>("/templates", template)
        : await api.patch<EmailTemplate>(`/templates/${id}`, template)
      ).data,
    onSuccess: () => templatesChanged(queryClient),
  });
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/templates/${id}`);
    },
    onSuccess: () => templatesChanged(queryClient),
  });
}
