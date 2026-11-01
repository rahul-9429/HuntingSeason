"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ContactPanel } from "@/components/inbox/contact-panel";
import { InboxSkeleton, ThreadDetailSkeleton } from "@/components/inbox/inbox-skeleton";
import { ThreadDetail } from "@/components/inbox/thread-detail";
import { ThreadList } from "@/components/inbox/thread-list";
import { LoadError } from "@/components/shared/load-error";
import { useToast } from "@/components/ui/toast";
import { usePrefetchThread, useThread, useThreads, useUpdateThread } from "@/lib/queries/threads";
import { useAppDispatch, useAppSelector } from "@/lib/store";
import { setFilter, setQuery } from "@/lib/store/inbox-slice";
import { useDebouncedValue } from "@/lib/use-debounced-value";
import { cn } from "@/lib/utils";

function selectInUrl(id: string) {
  window.history.replaceState(null, "", `?t=${id}`);
}

export function InboxView() {
  const filter = useAppSelector((state) => state.inbox.filter);
  const query = useAppSelector((state) => state.inbox.query);
  const dispatch = useAppDispatch();
  const q = useDebouncedValue(query.trim(), 250);
  const { data, isError, refetch } = useThreads(filter, q);
  const { mutate: updateThread } = useUpdateThread();
  const prefetchThread = usePrefetchThread();
  const [mobileDetail, setMobileDetail] = useState(false);
  const searchParams = useSearchParams();
  const toast = useToast();

  const threads = data?.items ?? [];
  const requestedId = searchParams.get("t");
  const selected = threads.find((t) => t.id === requestedId) ?? threads[0] ?? null;
  const { data: detail } = useThread(selected?.id);

  const selectedId = selected?.id;
  const selectedUnread = selected?.unread ?? false;
  useEffect(() => {
    if (selectedId && selectedUnread) updateThread({ id: selectedId, patch: { unread: false } });
  }, [selectedId, selectedUnread, updateThread]);

  if (isError) return <LoadError what="your inbox" onRetry={() => refetch()} className="m-6" />;
  if (!data) return <InboxSkeleton />;

  function archive(id: string) {
    const index = threads.findIndex((t) => t.id === id);
    const next = threads[index + 1] ?? threads[index - 1];
    updateThread({ id, patch: { archived: true } });
    if (next) selectInUrl(next.id);
    toast({
      title: "Conversation archived",
      action: {
        label: "Undo",
        onClick: () => {
          updateThread({ id, patch: { archived: false } });
          selectInUrl(id);
        },
      },
    });
  }

  return (
    <div className="flex h-full">
      <ThreadList
        threads={threads}
        selectedId={selected?.id ?? null}
        filter={filter}
        counts={data.counts}
        unreadTotal={data.unread}
        query={query}
        onFilterChange={(value) => dispatch(setFilter(value))}
        onQueryChange={(value) => dispatch(setQuery(value))}
        onPrefetch={prefetchThread}
        onSelect={(id) => {
          selectInUrl(id);
          setMobileDetail(true);
        }}
        className={cn("w-full md:w-[340px] md:shrink-0 lg:w-[372px]", mobileDetail && selected && "max-md:hidden")}
      />

      {selected ? (
        <>
          <div className={cn("min-w-0 flex-1", !mobileDetail && "max-md:hidden")}>
            {detail ? (
              <ThreadDetail
                key={detail.id}
                thread={detail}
                onBack={() => setMobileDetail(false)}
                onArchive={() => archive(detail.id)}
              />
            ) : (
              <ThreadDetailSkeleton />
            )}
          </div>
          {detail ? (
            <ContactPanel key={detail.id} thread={detail} className="hidden w-[300px] shrink-0 xl:block" />
          ) : (
            <div className="hidden w-[300px] shrink-0 border-l bg-canvas xl:block" />
          )}
        </>
      ) : (
        <div className="hidden flex-1 place-items-center bg-surface text-ui text-ink-3 md:grid">
          Select a conversation
        </div>
      )}
    </div>
  );
}
