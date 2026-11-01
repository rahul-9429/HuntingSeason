"use client";

import { LoaderCircle, TriangleAlert } from "lucide-react";
import { SettingsCardSkeleton } from "@/components/profile/settings-card";
import { ProviderTile } from "@/components/shared/brand-icons";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/api/client";
import { mailProviderLabel } from "@/lib/labels";
import { MAIL_PROVIDERS, useConnectMailbox, useDisconnectMailbox, useMailbox } from "@/lib/queries/mailbox";
import {
  useOutreachSettings,
  useUpdateOutreachSettings,
  type OutreachSettingsChanges,
} from "@/lib/queries/outreach";
import type { IntegrationId, MailProvider, Mailbox, OutreachSettings } from "@/lib/types";

const MAIL_PROVIDER_DESCRIPTIONS: Record<MailProvider, string> = {
  gmail: "Send outreach and follow-ups from your Gmail, and pick up the replies.",
  microsoft: "Send outreach and follow-ups from your Outlook or Microsoft 365, and pick up the replies.",
};

const COMING_SOON: { id: IntegrationId; name: string; description: string }[] = [
  { id: "google_calendar", name: "Google Calendar", description: "Offer your free times when someone wants to talk." },
];

const SETTINGS: {
  label: string;
  description: string;
  value: (settings: OutreachSettings) => boolean;
  change: (enabled: boolean) => OutreachSettingsChanges;
}[] = [
  {
    label: "Automatic outreach",
    description: "Email your new contacts and follow up a few minutes apart, up to your daily limit.",
    value: (settings) => settings.enabled,
    change: (enabled) => ({ enabled }),
  },
  {
    label: "Send reply drafts automatically",
    description: "Drafted answers to interested replies go out after 24 hours unless you edit or reject them.",
    value: (settings) => settings.auto_send_replies,
    change: (enabled) => ({ auto_send_replies: enabled }),
  },
];

const cardClass = "rounded-xl border-2 border-line-strong bg-surface";

export function IntegrationsTab() {
  const { data: mailbox } = useMailbox();

  if (mailbox === undefined) return <SettingsCardSkeleton />;

  return (
    <div className="space-y-4">
      <div className="px-1">
        <h2 className="text-[15px] font-semibold tracking-tight text-ink">Integrations</h2>
        <p className="mt-0.5 text-ui text-ink-2">
          Hunting Season sends from your own accounts so replies land where you already work.
        </p>
      </div>

      {mailbox ? (
        <MailboxCard mailbox={mailbox} />
      ) : (
        MAIL_PROVIDERS.map((provider) => <ConnectCard key={provider} provider={provider} />)
      )}

      {COMING_SOON.map(({ id, name, description }) => (
        <article key={id} className={cardClass}>
          <div className="flex flex-wrap items-start gap-4 p-5">
            <ProviderTile id={id} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-ui font-semibold text-ink">{name}</h3>
                <Badge tone="outline">Coming soon</Badge>
              </div>
              <p className="mt-0.5 text-ui text-ink-2">{description}</p>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

function ConnectButton({ provider, label, primary }: { provider: MailProvider; label: string; primary?: boolean }) {
  const connect = useConnectMailbox();
  const toast = useToast();
  const busy = connect.isPending || connect.isSuccess;

  return (
    <Button
      size="sm"
      variant={primary ? "primary" : "secondary"}
      disabled={busy}
      onClick={() =>
        connect.mutate(provider, {
          onError: (error) =>
            toast({ title: `Couldn't connect ${mailProviderLabel[provider]}`, description: errorMessage(error) }),
        })
      }
    >
      {busy && <LoaderCircle className="animate-spin" />}
      {busy ? "Connecting…" : label}
    </Button>
  );
}

function ConnectCard({ provider }: { provider: MailProvider }) {
  return (
    <article className={cardClass}>
      <div className="flex flex-wrap items-start gap-4 p-5">
        <ProviderTile id={provider} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-ui font-semibold text-ink">{mailProviderLabel[provider]}</h3>
            <Badge tone="outline">Not connected</Badge>
          </div>
          <p className="mt-0.5 text-ui text-ink-2">{MAIL_PROVIDER_DESCRIPTIONS[provider]}</p>
        </div>
        <ConnectButton provider={provider} label="Connect" />
      </div>
    </article>
  );
}

function MailboxCard({ mailbox }: { mailbox: Mailbox }) {
  const { data: settings } = useOutreachSettings();
  const update = useUpdateOutreachSettings();
  const disconnect = useDisconnectMailbox();
  const toast = useToast();
  const name = mailProviderLabel[mailbox.provider];
  const needsReconnect = mailbox.status === "needs_reconnect";

  function saveSetting(changes: OutreachSettingsChanges) {
    update.mutate(changes, {
      onError: (error) => toast({ title: "Couldn't save that setting", description: errorMessage(error) }),
    });
  }

  function disconnectMailbox() {
    disconnect.mutate(undefined, {
      onSuccess: () => toast({ title: `${name} disconnected`, description: "Outreach stops until you connect again" }),
      onError: (error) => toast({ title: `Couldn't disconnect ${name}`, description: errorMessage(error) }),
    });
  }

  return (
    <article className={cardClass}>
      <div className="flex flex-wrap items-start gap-4 p-5">
        <ProviderTile id={mailbox.provider} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-ui font-semibold text-ink">{name}</h3>
            {needsReconnect ? <Badge tone="amber">Needs reconnecting</Badge> : <Badge tone="accent">Connected</Badge>}
          </div>
          <p className="mt-0.5 text-ui text-ink-2">{MAIL_PROVIDER_DESCRIPTIONS[mailbox.provider]}</p>
          <p className="mt-1.5 font-mono text-micro text-ink-3">
            {mailbox.email} · {mailbox.sends_today} of {mailbox.daily_cap} emails sent today
          </p>
        </div>
        {needsReconnect ? (
          <ConnectButton provider={mailbox.provider} label="Reconnect" primary />
        ) : (
          <Button size="sm" variant="ghost" disabled={disconnect.isPending} onClick={disconnectMailbox}>
            Disconnect
          </Button>
        )}
      </div>

      {needsReconnect && (
        <p className="mx-5 mb-4 flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2.5 text-micro text-amber-900 ring-1 ring-inset ring-amber-200/70 dark:bg-amber-400/10 dark:text-amber-200 dark:ring-amber-400/20">
          <TriangleAlert className="mt-px size-3.5 shrink-0" />
          Access to {mailbox.email} expired or was revoked. Reconnect to keep sending and picking up replies.
        </p>
      )}

      {settings && (
        <ul className="divide-y border-t">
          {SETTINGS.map((setting) => (
            <li key={setting.label} className="flex items-center gap-4 px-5 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-ui text-ink">{setting.label}</p>
                <p className="text-micro text-ink-3">{setting.description}</p>
              </div>
              <Switch
                checked={setting.value(settings)}
                onCheckedChange={(enabled) => saveSetting(setting.change(enabled))}
                aria-label={setting.label}
              />
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
