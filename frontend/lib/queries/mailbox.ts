import { isAxiosError } from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { queryKeys } from "@/lib/queries/keys";
import type { MailProvider, Mailbox } from "@/lib/types";

export const MAIL_PROVIDERS: MailProvider[] = ["gmail", "microsoft"];

export const isMailProvider = (value: string): value is MailProvider =>
  (MAIL_PROVIDERS as string[]).includes(value);

export function mailboxRedirectUri(provider: MailProvider) {
  return `${window.location.origin}/connect/${provider}`;
}

export function useMailbox() {
  return useQuery({
    queryKey: queryKeys.mailbox,
    queryFn: async () => {
      try {
        return (await api.get<Mailbox>("/mailbox")).data;
      } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) return null;
        throw error;
      }
    },
  });
}

export function useConnectMailbox() {
  return useMutation({
    mutationFn: async (provider: MailProvider) =>
      (
        await api.get<{ url: string }>(`/mailbox/${provider}/auth-url`, {
          params: { redirect_uri: mailboxRedirectUri(provider) },
        })
      ).data,
    onSuccess: ({ url }) => window.location.assign(url),
  });
}

export function useFinishMailboxConnect() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ provider, url }: { provider: MailProvider; url: string }) =>
      (
        await api.post<Mailbox>("/mailbox/connect", {
          provider,
          url,
          redirect_uri: mailboxRedirectUri(provider),
        })
      ).data,
    onSuccess: (mailbox) => queryClient.setQueryData(queryKeys.mailbox, mailbox),
  });
}

export function useDisconnectMailbox() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.delete("/mailbox");
    },
    onSuccess: () => queryClient.setQueryData(queryKeys.mailbox, null),
  });
}
