"use client";

import { Mail, MapPin } from "lucide-react";
import { useState } from "react";
import { LinkedInGlyph } from "@/components/shared/brand-icons";
import { Avatar, CompanyMark } from "@/components/ui/avatar";
import { Textarea } from "@/components/ui/field";
import { useUpdateThread } from "@/lib/queries/threads";
import type { ThreadWithContact } from "@/lib/types";
import { cn, hueFor } from "@/lib/utils";

interface ContactPanelProps {
  thread: ThreadWithContact;
  className?: string;
}

export function ContactPanel({ thread, className }: ContactPanelProps) {
  const { contact } = thread;
  const { company } = contact;
  const [notes, setNotes] = useState(thread.notes);
  const { mutate: updateThread } = useUpdateThread();

  return (
    <aside aria-label="Contact details" className={cn("scrollbar-thin overflow-y-auto border-l bg-canvas", className)}>
      <section className="border-b px-5 py-5">
        <Avatar name={contact.name} size="xl" />
        <h3 className="mt-3 text-[15px] font-semibold tracking-tight text-ink">{contact.name}</h3>
        <p className="text-ui text-ink-2">{contact.title}</p>
        <p className="mt-1.5 flex items-center gap-1.5 text-ui font-medium text-ink">
          <CompanyMark name={company.name} hue={hueFor(company.name)} size="sm" />
          {company.name}
        </p>

        <dl className="mt-4 space-y-2 text-ui">
          <div className="flex items-center gap-2.5">
            <dt className="sr-only">Email</dt>
            <Mail className="size-3.5 shrink-0 text-ink-3" />
            <dd className="truncate font-mono text-micro text-ink-2">
              {contact.email ?? contact.emailMasked ?? "No public email"}
            </dd>
          </div>
          <div className="flex items-center gap-2.5">
            <dt className="sr-only">LinkedIn</dt>
            <LinkedInGlyph />
            <dd className="truncate text-ink-2">{contact.linkedin ?? "Not revealed"}</dd>
          </div>
          <div className="flex items-center gap-2.5">
            <dt className="sr-only">Location</dt>
            <MapPin className="size-3.5 text-ink-3" />
            <dd className="text-ink-2">{contact.location ?? "Unknown"}</dd>
          </div>
        </dl>
      </section>

      <section className="px-5 py-4">
        <h4 className="text-micro font-medium text-ink-3">Notes</h4>
        <Textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => {
            if (notes !== thread.notes) updateThread({ id: thread.id, patch: { notes } });
          }}
          rows={5}
          maxLength={5000}
          placeholder="Anything to remember before you reply…"
          aria-label="Notes"
          className="mt-2.5"
        />
        <p className="mt-1.5 text-micro text-ink-3">Only you can see these. Saved when you click away.</p>
      </section>
    </aside>
  );
}
