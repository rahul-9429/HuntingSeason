import {
  keepPreviousData,
  type QueryClient,
  skipToken,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { queryKeys } from "@/lib/queries/keys";
import type { InboxFilter, Message, ReplyDraft, ThreadList, ThreadPatch, ThreadWithContact } from "@/lib/types";

export function useThreads(filter: InboxFilter, q: string) {
  return useQuery({
    queryKey: queryKeys.threadList(filter, q),
    queryFn: async () => (await api.get<ThreadList>("/v1/threads", { params: { filter, q: q || undefined } })).data,
    placeholderData: keepPreviousData,
  });
}

const fetchThread = async (id: string) => (await api.get<ThreadWithContact>(`/v1/threads/${id}`)).data;

export function useThread(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.thread(id ?? ""),
    queryFn: id ? () => fetchThread(id) : skipToken,
  });
}

export function usePrefetchThread() {
  const queryClient = useQueryClient();
  return (id: string) => queryClient.prefetchQuery({ queryKey: queryKeys.thread(id), queryFn: () => fetchThread(id) });
}

function patchList(list: ThreadList, id: string, patch: ThreadPatch): ThreadList {
  const target = list.items.find((t) => t.id === id);
  if (!target) return list;
  const readNow = target.unread && (patch.archived === true || patch.unread === false);
  return {
    ...list,
    items: patch.archived
      ? list.items.filter((t) => t.id !== id)
      : list.items.map((t) => (t.id === id && patch.unread !== undefined ? { ...t, unread: patch.unread } : t)),
    unread: list.unread - (readNow ? 1 : 0),
  };
}

export function useUpdateThread() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, patch }: { id: string; patch: ThreadPatch }) =>
      (await api.patch<ThreadWithContact>(`/v1/threads/${id}`, patch)).data,
    onMutate: async ({ id, patch }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.threadLists });
      const previous = queryClient.getQueriesData<ThreadList>({ queryKey: queryKeys.threadLists });
      queryClient.setQueriesData<ThreadList>({ queryKey: queryKeys.threadLists }, (list) =>
        list ? patchList(list, id, patch) : list,
      );
      return { previous };
    },
    onError: (_error, _variables, context) =>
      context?.previous.forEach(([key, list]) => queryClient.setQueryData(key, list)),
    onSuccess: (thread) => queryClient.setQueryData(queryKeys.thread(thread.id), thread),
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.threadLists }),
  });
}

export function useReply() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: string }) =>
      (await api.post<Message>(`/v1/threads/${id}/messages`, { body })).data,
    onSuccess: (message, { id }) => {
      queryClient.setQueryData<ThreadWithContact>(queryKeys.thread(id), (thread) =>
        thread ? { ...thread, messages: [...thread.messages, message], updatedAt: message.sentAt } : thread,
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.thread(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.threadLists });
      void queryClient.invalidateQueries({ queryKey: queryKeys.mailbox });
    },
  });
}

function draftResolved(queryClient: QueryClient, threadId: string) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.thread(threadId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.threadLists });
}

export function useSendDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ draft, body }: { threadId: string; draft: ReplyDraft; body: string }) => {
      if (body.trim() !== draft.body.trim()) await api.patch(`/proposals/${draft.id}`, { body: body.trim() });
      await api.post(`/proposals/${draft.id}/approve`);
    },
    onSettled: (_, __, { threadId }) => {
      draftResolved(queryClient, threadId);
      void queryClient.invalidateQueries({ queryKey: queryKeys.mailbox });
    },
  });
}

export function useDismissDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ draft }: { threadId: string; draft: ReplyDraft }) => {
      await api.post(`/proposals/${draft.id}/reject`);
    },
    onSettled: (_, __, { threadId }) => draftResolved(queryClient, threadId),
  });
}
