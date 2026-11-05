"use client";

import { Radar, Send, Zap } from "lucide-react";
import Link from "next/link";
import { LiveDot } from "@/components/shared/live-dot";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/api/client";
import { mailProviderLabel } from "@/lib/labels";
import { useHuntSettings } from "@/lib/queries/hunt";
import { useMailbox } from "@/lib/queries/mailbox";
import { useOutreachSettings, useRunOutreach, useUpdateOutreachSettings } from "@/lib/queries/outreach";
import { cn } from "@/lib/utils";

export function OutreachBanner() {
  const { data: mailbox } = useMailbox();
  const { data: settings } = useOutreachSettings();
  const { data: hunt } = useHuntSettings();
  const update = useUpdateOutreachSettings();
  const run = useRunOutreach();
  const toast = useToast();

  if (mailbox === undefined || !settings) {
    return <div aria-hidden className="h-[74px] animate-pulse rounded-xl border-2 border-line-strong bg-surface" />;
  }

  const connected = mailbox?.status === "active";
  const blocked = connected && settings.enabled && Boolean(settings.blocker);
  const live = connected && settings.enabled && !blocked;

  function toggle(enabled: boolean) {
    update.mutate(
      { enabled },
      {
        onSuccess: (updated) =>
          toast({
            title: !enabled
              ? "Outreach paused"
              : updated.blocker
                ? "Outreach is on, but nothing will send yet"
                : "Outreach turned on",
            description: enabled ? (updated.blocker ?? undefined) : undefined,
          }),
        onError: (error) => toast({ title: "Couldn't change outreach", description: errorMessage(error) }),
      },
    );
  }

  function sendNow() {
    run.mutate(undefined, {
      onSuccess: () =>
        toast({
          title: "Sending now",
          description: "New contacts and due follow-ups go out a few minutes apart, up to today's limit.",
        }),
    });
  }

  let title: string;
  let detail: string;
  if (!mailbox) {
    title = "Connect your email to start outreach";
    detail = "Emails go out from your own Gmail or Outlook, so replies land in your inbox.";
  } else if (!connected) {
    title = `Reconnect ${mailProviderLabel[mailbox.provider]} to keep sending`;
    detail = `Access to ${mailbox.email} expired or was revoked.`;
  } else if (blocked) {
    title = "Outreach is on, but nothing will send yet";
    detail = settings.blocker ?? "";
  } else if (settings.enabled) {
    title = "Outreach is running";
    detail = `${mailbox.sends_today} of ${mailbox.daily_cap} emails sent today from ${mailbox.email}. New contacts are emailed a few minutes apart.`;
  } else {
    title = "Outreach is paused";
    detail = "Turn it on to email your contacts and follow up automatically.";
  }

  const huntBlocker = hunt && hunt.enabled ? hunt.blocker : null;

  return (
    <>
      <section
        aria-label="Outreach status"
        className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-xl border-2 border-line-strong bg-surface px-5 py-4"
      >
        <span
          className={cn(
            "grid size-9 shrink-0 place-items-center rounded-lg transition-colors",
            live && "bg-accent-50 text-accent-700",
            blocked && "bg-amber-50 text-amber-700 dark:bg-amber-400/10 dark:text-amber-300",
            !live && !blocked && "bg-sunken text-ink-3",
          )}
        >
          <Send className="size-[18px]" />
        </span>

        <div className="min-w-[min(100%,16rem)] flex-1">
          <p className="flex items-center gap-2 text-ui font-medium text-ink">
            {connected && <LiveDot live={live} />}
            {title}
          </p>
          <p className="mt-0.5 text-micro text-ink-3">
            {detail}
            {blocked && (
              <>
                {" "}
                <Link href="/profile?tab=outreach" className="font-medium text-ink-2 underline">
                  Fix it in Outreach settings
                </Link>
              </>
            )}
          </p>
        </div>

        {connected ? (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={run.isPending || blocked}
              onClick={sendNow}
              title={
                blocked
                  ? (settings.blocker ?? "")
                  : "Email the next contact or due follow-up as soon as the gap since the last email allows"
              }
            >
              <Zap className="text-accent-700" /> Send now
            </Button>
            <label className="flex cursor-pointer items-center gap-2.5 rounded-md border bg-canvas/60 py-1.5 pl-3 pr-2 text-ui text-ink-2">
              {live ? "On" : "Off"}
              <Switch checked={settings.enabled} onCheckedChange={toggle} aria-label="Automatic outreach" />
            </label>
          </div>
        ) : (
          <Button asChild size="sm" variant="primary">
            <Link href="/profile?tab=integrations">{mailbox ? "Reconnect" : "Connect email"}</Link>
          </Button>
        )}
      </section>
      {huntBlocker && (
        <p
          role="status"
          className="mt-3 flex flex-wrap items-center gap-x-1.5 gap-y-1 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-micro text-amber-800 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-200"
        >
          <Radar className="size-3.5" />
          <span className="font-medium">Auto-Hunt isn&apos;t finding new contacts.</span>
          {huntBlocker}{" "}
          <Link href="/profile?tab=targets" className="font-medium underline">
            Set your targets
          </Link>
        </p>
      )}
    </>
  );
}
