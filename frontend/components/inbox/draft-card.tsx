"use client";

import { Send, Sparkles } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { replyLabelText } from "@/lib/labels";
import { useDismissDraft, useSendDraft } from "@/lib/queries/threads";
import type { ReplyDraft } from "@/lib/types";

const sendsAt = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" });

export function DraftCard({ threadId, draft }: { threadId: string; draft: ReplyDraft }) {
  const [body, setBody] = useState(draft.body);
  const send = useSendDraft();
  const dismiss = useDismissDraft();
  const toast = useToast();
  const busy = send.isPending || dismiss.isPending;

  return (
    <article
      aria-label="Suggested reply"
      className="rounded-xl border border-dashed border-accent-300 bg-accent-50/40 p-4 dark:bg-accent-400/5"
    >
      <header className="flex flex-wrap items-center gap-2">
        <Sparkles className="size-3.5 text-accent-700" />
        <p className="text-ui font-medium text-ink">Suggested reply</p>
        <Badge tone="accent">{replyLabelText[draft.label]}</Badge>
        {draft.autoSendAt && (
          <span className="ml-auto text-micro text-ink-3">Sends by itself {sendsAt(draft.autoSendAt)}</span>
        )}
      </header>
      {draft.reason && <p className="mt-1 text-micro text-ink-3">{draft.reason}</p>}
      <Textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={7}
        aria-label="Suggested reply text"
        className="mt-3 leading-6"
      />
      <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
        <p className="mr-auto text-micro text-ink-3">Your signature is added when it&apos;s sent.</p>
        <Button
          size="sm"
          variant="ghost"
          disabled={busy}
          onClick={() => dismiss.mutate({ threadId, draft }, { onSuccess: () => toast({ title: "Draft dismissed" }) })}
        >
          Dismiss
        </Button>
        <Button
          size="sm"
          variant="primary"
          disabled={busy || !body.trim()}
          onClick={() => send.mutate({ threadId, draft, body }, { onSuccess: () => toast({ title: "Reply sent" }) })}
        >
          <Send /> {send.isPending ? "Sending…" : "Send reply"}
        </Button>
      </div>
    </article>
  );
}
