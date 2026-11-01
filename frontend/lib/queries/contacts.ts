import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { textToHtml } from "@/lib/email-text";
import { setCreditsLeft } from "@/lib/queries/companies";
import { queryKeys } from "@/lib/queries/keys";
import type { ContactFilter, ContactList, ContactWithCompany, Credits, Writer } from "@/lib/types";

type Cursor = string | null;

export type ContactPages = InfiniteData<ContactList, Cursor>;

export function useContacts(type: ContactFilter) {
  return useInfiniteQuery<ContactList, Error, ContactPages, readonly unknown[], Cursor>({
    queryKey: queryKeys.contactList(type),
    queryFn: async ({ pageParam }) =>
      (
        await api.get<ContactList>("/v1/contacts", {
          params: { ...(type === "all" ? {} : { type }), ...(pageParam ? { cursor: pageParam } : {}) },
        })
      ).data,
    initialPageParam: null,
    getNextPageParam: (last) => last.nextCursor,
    placeholderData: keepPreviousData,
  });
}

const PICKER_SIZE = 100;

export function useContactPicker() {
  return useQuery({
    queryKey: queryKeys.contactPicker,
    queryFn: async () =>
      (await api.get<ContactList>("/v1/contacts", { params: { limit: PICKER_SIZE } })).data,
  });
}

export function loadedContacts(data?: ContactPages): ContactWithCompany[] {
  const seen = new Set<string>();
  return (data?.pages.flatMap((page) => page.items) ?? []).filter((contact) => {
    if (seen.has(contact.id)) return false;
    seen.add(contact.id);
    return true;
  });
}

function patchContact(queryClient: QueryClient, id: string, patch: Partial<ContactWithCompany>) {
  queryClient.setQueriesData<ContactPages>(
    { queryKey: queryKeys.contacts },
    (data) =>
      data && {
        ...data,
        pages: data.pages.map((page) => ({
          ...page,
          items: page.items.map((c) => (c.id === id ? { ...c, ...patch } : c)),
        })),
      },
  );
}

export function useRevealContact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      (await api.post<{ contact: ContactWithCompany; credits: Credits }>(`/v1/contacts/${id}/reveal`)).data,
    onSuccess: ({ contact, credits }) => {
      patchContact(queryClient, contact.id, contact);
      queryClient.setQueryData(queryKeys.credits, credits);
      setCreditsLeft(queryClient, credits.total - credits.used);
    },
  });
}

export interface OutreachInput {
  contactId: string;
  subject: string;
  body: string;
  writer?: Writer;
  templateId?: number | null;
}

export function useSendOutreach() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ contactId, subject, body, writer, templateId }: OutreachInput) =>
      (
        await api.post<{ contact: ContactWithCompany; credits: Credits }>(`/v1/contacts/${contactId}/outreach`, {
          subject,
          html: textToHtml(body),
          writer,
          templateId,
        })
      ).data,
    onSuccess: ({ contact, credits }) => {
      patchContact(queryClient, contact.id, contact);
      queryClient.setQueryData(queryKeys.credits, credits);
      void queryClient.invalidateQueries({ queryKey: queryKeys.threads });
      void queryClient.invalidateQueries({ queryKey: queryKeys.mailbox });
    },
  });
}
