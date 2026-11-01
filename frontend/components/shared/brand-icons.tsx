import { CalendarDays, Mail } from "lucide-react";
import type { IntegrationId, MailProvider } from "@/lib/types";
import { cn } from "@/lib/utils";

export function GmailGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={cn("size-3.5", className)}>
      <path
        fill="#d64a3b"
        d="M2 6.6C2 5.7 2.7 5 3.6 5h.9l7.5 5.6L19.5 5h.9c.9 0 1.6.7 1.6 1.6v10.8c0 .9-.7 1.6-1.6 1.6H18V9.9l-6 4.5-6-4.5V19H3.6c-.9 0-1.6-.7-1.6-1.6V6.6Z"
      />
    </svg>
  );
}

export function LinkedInGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={cn("size-3.5", className)}>
      <rect width="22" height="22" x="1" y="1" rx="4" fill="#0a66c2" />
      <path
        fill="#fff"
        d="M6.3 9.6h2.6V18H6.3V9.6Zm1.3-4.1a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM10.6 9.6h2.5v1.2c.4-.7 1.2-1.4 2.6-1.4 2.7 0 3.2 1.8 3.2 4.1V18h-2.6v-4c0-1 0-2.2-1.4-2.2s-1.6 1.1-1.6 2.1V18h-2.7V9.6Z"
      />
    </svg>
  );
}

export function OutlookGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={cn("size-3.5", className)}>
      <rect width="22" height="22" x="1" y="1" rx="4" fill="#0a64ad" />
      <ellipse cx="12" cy="12" rx="4.6" ry="5.6" fill="none" stroke="#fff" strokeWidth="2.4" />
    </svg>
  );
}

export function ChannelIcon({ provider, className }: { provider?: MailProvider; className?: string }) {
  if (provider) return <MailProviderIcon provider={provider} className={className} />;
  return <Mail aria-hidden className={cn("size-3.5 text-ink-3", className)} />;
}

export function MailProviderIcon({ provider, className }: { provider: MailProvider; className?: string }) {
  return provider === "gmail" ? <GmailGlyph className={className} /> : <OutlookGlyph className={className} />;
}

export function ProviderTile({ id }: { id: IntegrationId }) {
  const glyph = {
    gmail: <GmailGlyph className="size-5" />,
    microsoft: <OutlookGlyph className="size-5" />,
    google_calendar: <CalendarDays className="size-5 text-[#1a73e8]" aria-hidden />,
  }[id];

  return (
    <span className="grid size-10 shrink-0 place-items-center rounded-lg border-2 border-line-strong bg-surface">
      {glyph}
    </span>
  );
}
