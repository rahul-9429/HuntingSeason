"use client";

import { Radar, TriangleAlert, Zap } from "lucide-react";
import { useState } from "react";
import { SettingRow, SettingsCard, SettingsCardSkeleton } from "@/components/profile/settings-card";
import { LoadError } from "@/components/shared/load-error";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/api/client";
import { useHuntSettings, useRunHunt, useUpdateHuntSettings } from "@/lib/queries/hunt";
import type { HuntSettings } from "@/lib/types";

function sinceLabel(at: string): string {
  const minutes = Math.round((Date.now() - new Date(at).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function lastRunLabel(settings: HuntSettings): string {
  if (!settings.last_run_at) {
    return settings.enabled ? "No hunt yet — the first one runs within the hour." : "No hunt yet.";
  }
  const companies = `${settings.companies_added} ${settings.companies_added === 1 ? "company" : "companies"}`;
  const contacts = `${settings.contacts_found} ${settings.contacts_found === 1 ? "contact" : "contacts"}`;
  return `Last hunt ${sinceLabel(settings.last_run_at)} · ${companies}, ${contacts}`;
}

function budgetLabel(budget: number, left: number): string {
  if (left === 0) return "Your balance is empty, so the next hunt finds nothing.";
  if (budget === 0) return "Auto-Hunt won't spend any credits — it will find nothing.";
  if (budget >= left)
    return "Auto-Hunt can spend the rest of your balance, leaving none for your own searches.";
  return `Auto-Hunt spends up to ${budget} per run. The other ${left - budget} in your balance stay for your own searches and reveals.`;
}

export function HuntCard() {
  const { data: settings, isError, error, refetch } = useHuntSettings();

  if (isError && !settings) {
    return (
      <LoadError what="Auto-Hunt settings" detail={errorMessage(error)} onRetry={() => void refetch()} />
    );
  }
  if (!settings) return <SettingsCardSkeleton />;
  return <HuntForm settings={settings} />;
}

function HuntForm({ settings }: { settings: HuntSettings }) {
  const update = useUpdateHuntSettings();
  const run = useRunHunt();
  const toast = useToast();
  const [budget, setBudget] = useState(settings.run_credit_budget);

  const blocked = settings.enabled && Boolean(settings.blocker);
  const live = settings.enabled && !blocked;

  function toggle(enabled: boolean) {
    update.mutate(
      { enabled },
      {
        onSuccess: (updated) =>
          toast({
            title: !enabled
              ? "Auto-Hunt paused"
              : updated.blocker
                ? "Auto-Hunt is on, but it has nothing to search on yet"
                : "Auto-Hunt turned on",
            description: enabled ? (updated.blocker ?? undefined) : undefined,
          }),
        onError: (mutationError) =>
          toast({ title: "Couldn't change Auto-Hunt", description: errorMessage(mutationError) }),
      },
    );
  }

  function commitBudget(value: number) {
    if (value === settings.run_credit_budget) return;
    update.mutate(
      { run_credit_budget: value },
      {
        onSuccess: () => toast({ title: `Auto-Hunt can spend ${value} credits per run` }),
        onError: (mutationError) => {
          setBudget(settings.run_credit_budget);
          toast({ title: "Couldn't save the credit budget", description: errorMessage(mutationError) });
        },
      },
    );
  }

  function huntNow() {
    run.mutate(undefined, {
      onSuccess: () =>
        toast({
          title: "Hunting now",
          description: "New companies and contacts appear on the Contacts page over the next few minutes.",
        }),
      onError: (mutationError) =>
        toast({ title: "Couldn't start the hunt", description: errorMessage(mutationError) }),
    });
  }

  return (
    <SettingsCard
      title="Auto-Hunt"
      description="Finds companies hiring for the roles and places below, then the people there worth emailing — on its own, once a day."
      action={
        <label className="flex cursor-pointer items-center gap-2.5 rounded-md border bg-canvas/60 py-1.5 pl-3 pr-2 text-ui text-ink-2">
          {live ? "On" : "Off"}
          <Switch checked={settings.enabled} onCheckedChange={toggle} aria-label="Auto-Hunt" />
        </label>
      }
    >
      <div className="divide-y">
        <SettingRow
          label={settings.enabled ? (blocked ? "On, but it can't hunt yet" : "Hunting daily") : "Paused"}
          description={blocked ? (settings.blocker ?? undefined) : lastRunLabel(settings)}
        >
          <div className="flex items-center gap-3">
            <span
              aria-hidden
              data-live={live}
              data-blocked={blocked}
              className="grid size-9 shrink-0 place-items-center rounded-lg bg-sunken text-ink-3 data-[blocked=true]:bg-amber-50 data-[blocked=true]:text-amber-700 data-[live=true]:bg-accent-50 data-[live=true]:text-accent-700 dark:data-[blocked=true]:bg-amber-400/10 dark:data-[blocked=true]:text-amber-300"
            >
              {blocked ? <TriangleAlert className="size-[18px]" /> : <Radar className="size-[18px]" />}
            </span>
            <Button size="sm" variant="secondary" disabled={run.isPending || blocked} onClick={huntNow}>
              <Zap className="text-accent-700" /> Hunt now
            </Button>
          </div>
        </SettingRow>

        <div className="py-3.5 last:pb-0">
          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
            <p className="text-ui font-medium text-ink">Credits Auto-Hunt may spend per run</p>
            <p className="text-micro text-ink-3">
              <span className="font-medium text-ink-2">{budget}</span> of {settings.run_credit_limit} ·{" "}
              {settings.credits_left} left in your balance
            </p>
          </div>
          <div className="mt-3 flex items-center gap-3">
            <Slider
              value={budget}
              max={settings.run_credit_limit}
              step={5}
              disabled={!settings.enabled}
              onValueChange={setBudget}
              onCommit={commitBudget}
              aria-label="Credits Auto-Hunt may spend per run"
              valueText={`${budget} of ${settings.run_credit_limit} credits`}
            />
          </div>
          <p className="mt-2 text-micro text-ink-3">{budgetLabel(budget, settings.credits_left)}</p>
          <p className="mt-1 text-micro text-ink-3">
            Credits come out of your balance and roll over — they don’t expire. One search
            finds up to 100 companies for a single credit. After that it is one credit per
            contact revealed, at most two per company.
          </p>
        </div>
      </div>
    </SettingsCard>
  );
}
