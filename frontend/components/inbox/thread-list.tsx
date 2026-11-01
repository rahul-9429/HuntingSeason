"use client";

import { Inbox, Search } from "lucide-react";
import { IntegrationStatus } from "@/components/inbox/integration-status";
import { ChannelIcon } from "@/components/shared/brand-icons";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { useMailbox } from "@/lib/queries/mailbox";
import type { InboxFilter, ThreadSummary } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";

const inboxFilters: { value: InboxFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "drafts", label: "Needs approval" },
  { value: "recruiter", label: "Recruiters" },
  { value: "hiring_manager", label: "Hiring managers" },
  { value: "referrer", label: "Referrals" },
];

interface ThreadListProps {
  threads: ThreadSummary[];
  selectedId: string | null;
  filter: InboxFilter;
  counts: Record<InboxFilter, number>;
  unreadTotal: number;
  query: string;
  onFilterChange: (filter: InboxFilter) => void;
  onQueryChange: (query: string) => void;
  onPrefetch: (id: string) => void;
  onSelect: (id: string) => void;
  className?: string;
}

export function ThreadList({
  threads,
  selectedId,
  filter,
  counts,
  unreadTotal,
  query,
  onFilterChange,
  onQueryChange,
  onPrefetch,
  onSelect,
  className,
}: ThreadListProps) {
  const { data: mailbox } = useMailbox();
  const emptyText = query
    ? "No conversations match your search."
    : filter === "drafts"
      ? "No suggested replies are waiting for you."
      : "You're all caught up in this view.";

  return (
    <section aria-label="Conversations" className={cn("flex min-h-0 flex-col border-r bg-surface", className)}>
      <div className="px-4 pt-5">
        <div className="flex items-center justify-between gap-3">
          <h1 className="font-serif text-[30px] leading-none text-ink">Inbox</h1>
          <IntegrationStatus />
        </div>
        <p className="mt-1.5 text-micro text-ink-3">{unreadTotal} unread</p>

        <div className="relative mt-4">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-3" />
          <input
            type="search"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Search people, companies, subjects"
            className="h-8 w-full rounded-md border bg-canvas/60 pl-8 pr-3 text-ui text-ink outline-none transition placeholder:text-ink-3 focus:border-accent-400 focus:bg-surface focus:ring-2 focus:ring-accent-500/15"
          />
        </div>
      </div>

      <div role="tablist" aria-label="Filter conversations" className="mt-3 flex gap-4 overflow-x-auto border-b px-4 [scrollbar-width:none]">
        {inboxFilters.map((f) => {
          const active = filter === f.value;
          const count = counts[f.value] ?? 0;
          const waiting = f.value === "drafts" && count > 0;
          return (
            <button
              key={f.value}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onFilterChange(f.value)}
              className={cn(
                "relative flex h-9 shrink-0 cursor-pointer items-center gap-1.5 whitespace-nowrap text-ui outline-none transition-colors focus-visible:text-ink",
                active ? "font-medium text-ink" : "text-ink-3 hover:text-ink-2",
              )}
            >
              {f.label}
              <span
                className={cn(
                  "font-mono text-micro tabular-nums",
                  waiting ? "font-medium text-accent-700" : "text-ink-3",
                )}
              >
                {count}
              </span>
              {active && <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-ink" />}
            </button>
          );
        })}
      </div>

      <ul className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
        {threads.map((thread) => {
          const selected = thread.id === selectedId;
          const last = thread.lastMessage;
          return (
            <li key={thread.id}>
              <button
                type="button"
                onPointerEnter={() => onPrefetch(thread.id)}
                onFocus={() => onPrefetch(thread.id)}
                onClick={() => onSelect(thread.id)}
                aria-current={selected ? "true" : undefined}
                className={cn(
                  "relative flex w-full cursor-pointer gap-3 border-b border-line/70 px-4 py-3 text-left outline-none transition-colors focus-visible:bg-sunken",
                  selected ? "bg-sunken" : "hover:bg-canvas",
                )}
              >
                {selected && <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-accent-600" />}
                <Avatar name={thread.contact.name} size="sm" className="mt-0.5" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    {thread.unread && <span className="size-1.5 shrink-0 rounded-full bg-accent-600" aria-label="Unread" />}
                    <span className={cn("truncate text-ui text-ink", thread.unread ? "font-semibold" : "font-medium")}>
                      {thread.contact.name}
                    </span>
                    <span className="truncate text-micro text-ink-3">{thread.contact.company.name}</span>
                    <span className="ml-auto flex shrink-0 items-center gap-1.5 pl-2 text-micro tabular-nums text-ink-3">
                      <ChannelIcon provider={mailbox?.provider} className="size-3" />
                      {timeAgo(thread.updatedAt)}
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5">
                    <p className={cn("truncate text-ui", thread.unread ? "font-medium text-ink" : "text-ink-2")}>
                      {thread.subject}
                    </p>
                    {thread.hasDraft && (
                      <Badge tone="accent" className="ml-auto">
                        Draft
                      </Badge>
                    )}
                  </div>
                  <p className="truncate text-ui text-ink-3">
                    {last.from === "me" && <span className="text-ink-2">You: </span>}
                    {last.body.replace(/\s+/g, " ")}
                  </p>
                </div>
              </button>
            </li>
          );
        })}

        {threads.length === 0 && (
          <li className="px-6 py-16 text-center">
            <Inbox className="mx-auto size-5 text-ink-3" />
            <p className="mt-2 text-ui font-medium text-ink">Nothing here</p>
            <p className="mt-1 text-micro text-ink-3">{emptyText}</p>
          </li>
        )}
      </ul>
    </section>
  );
}
