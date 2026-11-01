"use client";

import Link from "next/link";
import { ChannelIcon } from "@/components/shared/brand-icons";
import { Tooltip } from "@/components/ui/tooltip";
import { mailProviderLabel } from "@/lib/labels";
import { useMailbox } from "@/lib/queries/mailbox";
import { cn } from "@/lib/utils";

export function IntegrationStatus() {
  const { data: mailbox } = useMailbox();
  if (mailbox === undefined) return null;

  const ok = mailbox?.status === "active";
  const content = !mailbox
    ? "No mailbox connected"
    : ok
      ? `${mailProviderLabel[mailbox.provider]} connected · ${mailbox.email}`
      : `${mailProviderLabel[mailbox.provider]} needs reconnecting — click to fix`;

  return (
    <Tooltip side="bottom" content={content}>
      <Link
        href="/profile?tab=integrations"
        aria-label={`Mailbox: ${ok ? "connected" : "needs attention"}`}
        className="flex h-6 items-center gap-1.5 rounded-md border-2 border-line-strong bg-surface px-1.5 transition hover:border-line-strong"
      >
        <ChannelIcon provider={mailbox?.provider} className="size-3" />
        <span className={cn("size-1.5 rounded-full", ok ? "bg-accent-500" : "bg-amber-500")} />
      </Link>
    </Tooltip>
  );
}
