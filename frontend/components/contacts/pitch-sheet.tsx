"use client";

import { LoaderCircle, RefreshCw, Send } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { errorMessage } from "@/lib/api/client";
import { htmlToText } from "@/lib/email-text";
import { mailProviderLabel } from "@/lib/labels";
import { buildDraft } from "@/lib/outreach";
import { useMailbox } from "@/lib/queries/mailbox";
import { useOutreachPreview } from "@/lib/queries/outreach";
import { useProfile } from "@/lib/queries/profile";
import type { ContactWithCompany, UserProfile, Writer } from "@/lib/types";

export interface PitchDraft {
  subject: string;
  body: string;
  writer?: Writer;
  templateId?: number | null;
}

interface PitchSheetProps {
  contact: ContactWithCompany | null;
  sending: boolean;
  onClose: () => void;
  onSend: (contact: ContactWithCompany, draft: PitchDraft) => void;
}

export function PitchSheet({ contact, onClose, ...props }: PitchSheetProps) {
  const { data: user } = useProfile();

  return (
    <Sheet open={contact !== null} onOpenChange={(open) => !open && onClose()}>
      {contact && (
        <SheetContent>
          {user ? (
            <PitchForm key={contact.id} contact={contact} user={user} {...props} />
          ) : (
            <div aria-hidden className="m-6 h-72 animate-pulse rounded-lg bg-sunken" />
          )}
        </SheetContent>
      )}
    </Sheet>
  );
}

function PitchForm({
  contact,
  user,
  sending,
  onSend,
}: Omit<PitchSheetProps, "contact" | "onClose"> & { contact: ContactWithCompany; user: UserProfile }) {
  const { data: mailbox } = useMailbox();
  const canPreview = Boolean(contact.email) && Boolean(mailbox);
  const preview = useOutreachPreview(canPreview ? contact.id : null);
  const [edited, setEdited] = useState<PitchDraft | null>(null);
  const address = contact.email ?? contact.emailMasked;
  const active = mailbox?.status === "active";

  const waiting = mailbox === undefined || (canPreview && !preview.data && !preview.isError);
  const suggested: PitchDraft | null = waiting
    ? null
    : preview.data
      ? {
          subject: preview.data.subject,
          body: htmlToText(preview.data.html),
          writer: preview.data.writer,
          templateId: preview.data.template_id,
        }
      : buildDraft(contact, user);
  const draft = edited ?? suggested;

  function change(field: "subject" | "body", value: string) {
    if (draft) setEdited({ ...draft, [field]: value });
  }

  function rewrite() {
    setEdited(null);
    void preview.refetch();
  }

  let note: React.ReactNode = null;
  if (!mailbox && mailbox !== undefined) {
    note = (
      <>
        <Link href="/profile?tab=integrations" className="font-medium text-accent-700 hover:text-accent-800">
          Connect your email
        </Link>{" "}
        to send this from your own inbox.
      </>
    );
  } else if (mailbox && !active) {
    note = (
      <>
        <Link href="/profile?tab=integrations" className="font-medium text-accent-700 hover:text-accent-800">
          Reconnect {mailProviderLabel[mailbox.provider]}
        </Link>{" "}
        to send.
      </>
    );
  } else if (preview.data) {
    note =
      preview.data.writer === "email_agent"
        ? "Written by the email agent from your profile. Edit anything before you send."
        : "From your default template, personalized for them. Edit anything before you send.";
  } else if (preview.isError) {
    note = (
      <>
        Couldn&apos;t write a draft ({errorMessage(preview.error)}), so here&apos;s a starting point.{" "}
        <Link href="/profile?tab=outreach" className="font-medium text-accent-700 hover:text-accent-800">
          Set up your writer
        </Link>{" "}
        to get drafts written for you.
      </>
    );
  }

  const ready = Boolean(draft?.subject.trim() && draft.body.trim());

  return (
    <>
      <SheetHeader>
        <div className="flex items-center gap-3">
          <Avatar name={contact.name} size="lg" />
          <div className="min-w-0">
            <SheetTitle>Outreach to {contact.name}</SheetTitle>
            <SheetDescription className="mt-0.5 truncate">
              {contact.title} · {contact.company.name}
            </SheetDescription>
          </div>
        </div>
      </SheetHeader>

      <div className="scrollbar-thin flex-1 overflow-y-auto px-6 py-5">
        <div className="overflow-hidden rounded-lg border focus-within:border-accent-400 focus-within:ring-2 focus-within:ring-accent-500/15">
          <div className="flex items-center gap-2 border-b px-3 py-2 text-ui">
            <span className="w-14 shrink-0 text-micro text-ink-3">To</span>
            <span className="shrink-0 whitespace-nowrap font-medium text-ink">{contact.name}</span>
            <span className="min-w-0 truncate font-mono text-micro text-ink-3">{address ?? "No email address"}</span>
            {address && !contact.email && (
              <span className="ml-auto shrink-0 whitespace-nowrap text-micro text-ink-3">Reveals on send · 1 credit</span>
            )}
          </div>
          {draft ? (
            <>
              <div className="flex items-center gap-2 border-b px-3">
                <label htmlFor="pitch-subject" className="w-14 shrink-0 text-micro text-ink-3">
                  Subject
                </label>
                <input
                  id="pitch-subject"
                  value={draft.subject}
                  onChange={(e) => change("subject", e.target.value)}
                  className="h-9 flex-1 bg-transparent text-ui font-medium text-ink outline-none"
                />
              </div>
              <textarea
                aria-label="Message"
                value={draft.body}
                onChange={(e) => change("body", e.target.value)}
                rows={14}
                className="block w-full resize-none bg-surface px-3 py-3 text-ui leading-6 text-ink outline-none"
              />
            </>
          ) : (
            <div className="space-y-3 px-3 py-4" aria-live="polite">
              <p className="flex items-center gap-2 text-micro text-ink-3">
                <LoaderCircle className="size-3.5 animate-spin" /> Writing a draft for {contact.name}…
              </p>
              <div aria-hidden className="h-56 animate-pulse rounded-md bg-sunken" />
            </div>
          )}
        </div>

        <div className="mt-2.5 flex flex-wrap items-start justify-between gap-x-4 gap-y-1.5">
          <p className="min-w-0 flex-1 text-micro text-ink-3">
            {note}
            {draft && <span className="block">Links: [text](https://…) or paste the URL.</span>}
          </p>
          {canPreview && (
            <Button size="sm" variant="ghost" onClick={rewrite} disabled={preview.isFetching}>
              <RefreshCw className={preview.isFetching ? "animate-spin" : undefined} />
              {preview.isFetching ? "Writing…" : "Rewrite"}
            </Button>
          )}
        </div>
      </div>

      <SheetFooter className="justify-end">
        <Button
          variant="primary"
          disabled={!draft || !ready || !address || !active || sending}
          onClick={() => draft && onSend(contact, draft)}
        >
          {sending ? <LoaderCircle className="animate-spin" /> : <Send />}
          {address ? `Send via ${mailbox ? mailProviderLabel[mailbox.provider] : "email"}` : "No email to send to"}
        </Button>
      </SheetFooter>
    </>
  );
}
