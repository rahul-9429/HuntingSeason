"use client";

import { Archive, ArrowLeft, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { DraftCard } from "@/components/inbox/draft-card";
import { ChannelIcon } from "@/components/shared/brand-icons";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { channelLabel, mailProviderLabel } from "@/lib/labels";
import { useMailbox } from "@/lib/queries/mailbox";
import { useProfile } from "@/lib/queries/profile";
import { useReply } from "@/lib/queries/threads";
import type { ThreadWithContact } from "@/lib/types";
import { cn, firstName } from "@/lib/utils";

const sentAt = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

interface ThreadDetailProps {
  thread: ThreadWithContact;
  onBack: () => void;
  onArchive: () => void;
}

export function ThreadDetail({ thread, onBack, onArchive }: ThreadDetailProps) {
  const { contact } = thread;
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const { data: user } = useProfile();
  const { data: mailbox } = useMailbox();
  const provider = mailbox?.provider;
  const reply = useReply();
  const toast = useToast();

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [thread.messages.length, thread.draft?.id]);

  return (
    <section aria-label="Conversation" className="flex h-full min-w-0 flex-col bg-surface">
      <header className="border-b px-5 pb-3 pt-4 lg:px-6">
        <div className="flex items-start gap-2">
          <Button variant="ghost" size="icon-sm" onClick={onBack} className="-ml-1.5 md:hidden" aria-label="Back to list">
            <ArrowLeft />
          </Button>
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-1.5 text-micro text-ink-3">
              <ChannelIcon provider={provider} className="size-3" />
              {provider ? mailProviderLabel[provider] : channelLabel[thread.channel]}
            </p>
            <h2 className="mt-1 text-[17px] font-semibold leading-snug tracking-tight text-ink">{thread.subject}</h2>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={onArchive}>
            <Archive /> Archive
          </Button>
        </div>
      </header>

      <div ref={scrollRef} className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 py-6 lg:px-6">
        <div className="mx-auto max-w-2xl space-y-4">
          {thread.messages.map((message) => {
            const mine = message.from === "me";
            return (
              <article
                key={message.id}
                className={cn("rounded-xl border p-4", mine ? "bg-canvas/50" : "bg-surface")}
              >
                <header className="flex items-center gap-2.5">
                  <Avatar name={mine ? (user?.name ?? "You") : contact.name} hue={mine ? "ink" : undefined} size="sm" />
                  <p className="text-ui font-medium text-ink">{mine ? "You" : contact.name}</p>
                  <time dateTime={message.sentAt} className="ml-auto shrink-0 text-micro text-ink-3">
                    {sentAt(message.sentAt)}
                  </time>
                </header>
                <p className="mt-3 whitespace-pre-line text-ui leading-6 text-ink-2">{message.body}</p>
              </article>
            );
          })}
          {thread.draft && <DraftCard key={thread.draft.id} threadId={thread.id} draft={thread.draft} />}
        </div>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const body = draft.trim();
          if (!body) return;
          reply.mutate(
            { id: thread.id, body },
            {
              onSuccess: () => {
                setDraft("");
                toast({ title: "Reply sent" });
              },
            },
          );
        }}
        className="border-t px-5 py-4 lg:px-6"
      >
        <div className="rounded-xl border-2 border-line-strong bg-surface transition focus-within:border-accent-400 focus-within:ring-2 focus-within:ring-accent-500/15">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            placeholder={`Reply to ${firstName(contact.name)}…`}
            aria-label={`Reply to ${contact.name}`}
            className="block w-full resize-none bg-transparent px-3.5 pt-3 text-ui leading-6 text-ink outline-none placeholder:text-ink-3"
          />
          <div className="flex items-center justify-between gap-2 px-2.5 pb-2.5">
            <span className="flex min-w-0 items-center gap-1.5 truncate text-micro text-ink-3">
              <ChannelIcon provider={provider} className="size-3" />
              {`From ${mailbox?.email ?? "your email"}`}
            </span>
            <Button type="submit" variant="primary" size="sm" disabled={!draft.trim() || reply.isPending}>
              <Send /> Send
            </Button>
          </div>
        </div>
      </form>
    </section>
  );
}
