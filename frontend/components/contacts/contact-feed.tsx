"use client";

import { LoaderCircle, SearchX } from "lucide-react";
import Link from "next/link";
import { ContactCard } from "@/components/contacts/contact-card";
import { PitchSheet, type PitchDraft } from "@/components/contacts/pitch-sheet";
import { LoadError } from "@/components/shared/load-error";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/api/client";
import { contactTypePlural } from "@/lib/labels";
import { loadedContacts, useContacts, useRevealContact, useSendOutreach } from "@/lib/queries/contacts";
import { useOutreachCompanies } from "@/lib/queries/outreach";
import { useAppDispatch, useAppSelector } from "@/lib/store";
import { closePitch, openPitch, setType } from "@/lib/store/contacts-slice";
import type { ContactType, ContactWithCompany } from "@/lib/types";
import { cn, firstName } from "@/lib/utils";

const CONTACT_TYPES: ContactType[] = ["hiring_manager", "recruiter", "referrer"];

function FeedSkeleton() {
  return (
    <div aria-hidden className="mt-4 space-y-3">
      {Array.from({ length: 3 }, (_, i) => (
        <div key={i} className="flex animate-pulse gap-4 rounded-xl border-2 border-line-strong bg-surface p-5">
          <div className="size-10 rounded-full bg-sunken" />
          <div className="flex-1 space-y-2.5">
            <div className="h-4 w-1/3 rounded bg-sunken" />
            <div className="h-3 w-2/3 rounded bg-sunken" />
            <div className="h-3 w-1/2 rounded bg-sunken" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ContactFeed() {
  const type = useAppSelector((state) => state.contacts.type);
  const pitchContactId = useAppSelector((state) => state.contacts.pitchContactId);
  const dispatch = useAppDispatch();
  const feed = useContacts(type);
  const { data, isError, refetch, isPlaceholderData } = feed;
  const { data: outreach } = useOutreachCompanies();
  const reveal = useRevealContact();
  const send = useSendOutreach();
  const toast = useToast();

  const counts = data?.pages[0]?.counts;
  const contacts = loadedContacts(data);
  const pitchFor = contacts.find((c) => c.id === pitchContactId) ?? null;
  const searchingAt = outreach?.filter((c) => c.status === "searching").length ?? 0;

  function revealContact(contact: ContactWithCompany) {
    reveal.mutate(contact.id, {
      onSuccess: ({ contact: revealed, credits }) =>
        toast({
          title: revealed.email ? "Contact revealed" : "Contact revealed, but no verified email",
          description: `${credits.total - credits.used} credits left`,
        }),
    });
  }

  function sendOutreach(contact: ContactWithCompany, draft: PitchDraft) {
    send.mutate(
      { contactId: contact.id, ...draft },
      {
        onSuccess: () => {
          dispatch(closePitch());
          toast({
            title: `Email sent to ${firstName(contact.name)}`,
            description: "You'll see the conversation in your inbox.",
          });
        },
      },
    );
  }

  return (
    <section aria-labelledby="feed-heading" className="min-w-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="feed-heading" className="text-[15px] font-semibold tracking-tight text-ink">
          New contacts
        </h2>
        {searchingAt > 0 && (
          <p className="flex items-center gap-1.5 text-micro text-ink-3">
            <LoaderCircle className="size-3.5 animate-spin" />
            Finding contacts at {searchingAt} {searchingAt === 1 ? "company" : "companies"}…
          </p>
        )}
      </div>

      <Segmented
        aria-label="Contact type"
        value={type}
        onValueChange={(value) => dispatch(setType(value))}
        className="mt-3"
        options={[
          { value: "all", label: "All", count: counts?.all },
          ...CONTACT_TYPES.map((value) => ({
            value,
            label: contactTypePlural[value],
            count: counts?.[value],
          })),
        ]}
      />

      {isError && !data ? (
        <LoadError
          what="contacts"
          detail={errorMessage(feed.error)}
          onRetry={() => refetch()}
          className="mt-4"
        />
      ) : !data ? (
        <FeedSkeleton />
      ) : (
        <div className={cn("mt-4 space-y-3 transition-opacity", isPlaceholderData && "opacity-60")}>
          {contacts.map((contact) => (
            <ContactCard
              key={contact.id}
              contact={contact}
              revealing={reveal.isPending && reveal.variables === contact.id}
              onReveal={() => revealContact(contact)}
              onDraft={() => dispatch(openPitch(contact.id))}
            />
          ))}

          {contacts.length === 0 && (
            <div className="rounded-xl border border-dashed bg-surface/60 px-6 py-14 text-center">
              <SearchX className="mx-auto size-5 text-ink-3" />
              <p className="mt-2 text-ui font-medium text-ink">No contacts of this type yet</p>
              <p className="mt-1 text-micro text-ink-3">
                Use “Add to contacts” on a company in{" "}
                <Link href="/companies" className="font-medium text-accent-700 hover:text-accent-800">
                  Companies
                </Link>{" "}
                to find people there.
              </p>
            </div>
          )}

          {(feed.hasNextPage || feed.isFetchNextPageError) && (
            <div className="flex flex-col items-center gap-2 pt-3 text-center">
              {feed.isFetchNextPageError && (
                <p role="alert" className="text-ui text-ink-2">
                  {errorMessage(feed.error)}
                </p>
              )}
              <Button onClick={() => feed.fetchNextPage()} disabled={feed.isFetchingNextPage}>
                {feed.isFetchingNextPage && <LoaderCircle className="animate-spin" />}
                {feed.isFetchNextPageError ? "Try again" : "Load more"}
              </Button>
            </div>
          )}
        </div>
      )}

      <PitchSheet
        contact={pitchFor}
        sending={send.isPending}
        onClose={() => dispatch(closePitch())}
        onSend={sendOutreach}
      />
    </section>
  );
}
