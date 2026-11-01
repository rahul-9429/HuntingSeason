"use client";

import {
  Activity,
  BriefcaseBusiness,
  Check,
  GraduationCap,
  Layers,
  Mail,
  MapPin,
  Send,
  Users,
  type LucideIcon,
} from "lucide-react";
import { LinkedInGlyph } from "@/components/shared/brand-icons";
import { ContactTypeBadge } from "@/components/shared/contact-badges";
import { ScoreRing } from "@/components/shared/score-ring";
import { Avatar, CompanyMark } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { outreachStageLabel } from "@/lib/labels";
import { useApolloCreditsLeft } from "@/lib/queries/companies";
import type { ContactWithCompany, Signal } from "@/lib/types";
import { cn, hueFor, timeAgo } from "@/lib/utils";

const signalIcon: Record<Signal["kind"], LucideIcon> = {
  hiring: BriefcaseBusiness,
  background: GraduationCap,
  stack: Layers,
  activity: Activity,
  network: Users,
};

interface ContactCardProps {
  contact: ContactWithCompany;
  revealing: boolean;
  onReveal: () => void;
  onDraft: () => void;
}

export function ContactCard({ contact, revealing, onReveal, onDraft }: ContactCardProps) {
  const { company } = contact;
  const address = contact.email ?? contact.emailMasked;
  const noCreditsLeft = useApolloCreditsLeft() === 0;

  return (
    <article className="rounded-xl border-2 border-line-strong bg-surface transition-colors hover:border-line-strong">
      <div className="flex gap-4 p-5">
        <Avatar name={contact.name} size="lg" />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <h3 className="text-[15px] font-semibold tracking-tight text-ink">{contact.name}</h3>
            <ContactTypeBadge type={contact.type} />
            <span className="text-micro text-ink-3">New · {timeAgo(contact.foundAt)}</span>
          </div>

          <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-ui text-ink-2">
            {contact.title}
            <span className="text-ink-3">at</span>
            <span className="inline-flex items-center gap-1.5 font-medium text-ink">
              <CompanyMark name={company.name} hue={hueFor(company.name)} size="xs" />
              {company.name}
            </span>
          </p>

          <ul className="mt-3 space-y-1.5">
            {contact.signals.map((signal) => {
              const Icon = signalIcon[signal.kind];
              return (
                <li key={signal.label} className="flex items-start gap-2 text-ui text-ink-2">
                  <Icon
                    className={cn(
                      "mt-[3px] size-3.5 shrink-0",
                      signal.kind === "hiring" ? "text-accent-700" : "text-ink-3",
                    )}
                  />
                  {signal.label}
                </li>
              );
            })}
          </ul>
        </div>

        <div className="flex flex-col items-center gap-0.5">
          <ScoreRing value={contact.relevance} />
          <span className="text-[10px] text-ink-3">match</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t px-5 py-2.5 text-micro text-ink-2">
        {address ? (
          <span className="flex items-center gap-2">
            <Mail className="size-3.5 text-ink-3" />
            <span className="font-mono text-ink">{address}</span>
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-ink-3">
            <Mail className="size-3.5" />
            No public email
          </span>
        )}
        {!contact.revealed && (
          <button
            type="button"
            onClick={onReveal}
            disabled={revealing || noCreditsLeft}
            title={
              noCreditsLeft
                ? "You're out of credits"
                : "Shows their full name, LinkedIn and verified email. Uses 1 credit."
            }
            className="cursor-pointer font-medium text-accent-700 hover:text-accent-800 disabled:cursor-default disabled:opacity-60"
          >
            {revealing ? "Revealing…" : "Reveal · 1 credit"}
          </button>
        )}
        {contact.linkedin && (
          <a
            href={contact.linkedin}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 hover:text-ink"
          >
            <LinkedInGlyph />
            LinkedIn
          </a>
        )}
        {contact.location && (
          <span className="flex items-center gap-1.5">
            <MapPin className="size-3.5 text-ink-3" />
            {contact.location}
          </span>
        )}

        {contact.stage !== "new" ? (
          <span className="ml-auto flex items-center gap-1.5 px-1 text-micro text-ink-2">
            <Check className="size-3.5 text-accent-700" />
            {outreachStageLabel[contact.stage]}
          </span>
        ) : (
          <Button size="sm" variant="secondary" onClick={onDraft} className="ml-auto">
            <Send className="text-accent-700" />
            Draft outreach
          </Button>
        )}
      </div>
    </article>
  );
}
