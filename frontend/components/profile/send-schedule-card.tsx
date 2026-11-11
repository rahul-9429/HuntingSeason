"use client";

import { SettingsCard, SettingsCardSkeleton } from "@/components/profile/settings-card";
import { LoadError } from "@/components/shared/load-error";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/api/client";
import { useEmailSendSchedule, useUpdateEmailSendSchedule } from "@/lib/queries/outreach";
import type { EmailSendSchedule, SendScheduleRow } from "@/lib/types";
import { cn } from "@/lib/utils";

const DAYS = [
  { iso: 1, initial: "M", name: "Monday", short: "Mon" },
  { iso: 2, initial: "T", name: "Tuesday", short: "Tue" },
  { iso: 3, initial: "W", name: "Wednesday", short: "Wed" },
  { iso: 4, initial: "T", name: "Thursday", short: "Thu" },
  { iso: 5, initial: "F", name: "Friday", short: "Fri" },
  { iso: 6, initial: "S", name: "Saturday", short: "Sat" },
  { iso: 7, initial: "S", name: "Sunday", short: "Sun" },
];

function hourLabel(hour: number): string {
  const suffix = hour < 12 || hour === 24 ? "am" : "pm";
  const twelve = hour % 12 === 0 ? 12 : hour % 12;
  return `${twelve}${suffix}`;
}

function zoneLabel(zone: string): string {
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: zone,
      timeZoneName: "short",
    }).formatToParts(new Date());
    return parts.find((part) => part.type === "timeZoneName")?.value ?? zone;
  } catch {
    return zone;
  }
}

function windowLabel(row: SendScheduleRow): string {
  const hours = `${hourLabel(row.start_hour)}–${hourLabel(row.end_hour)}`;
  return row.timezone ? `${hours} local · ${zoneLabel(row.timezone)}` : `${hours} · no local conversion`;
}

function daysLabel(days: number[]): string {
  return DAYS.filter((day) => days.includes(day.iso))
    .map((day) => day.short)
    .join(", ");
}

export function SendScheduleCard() {
  const { data: schedule, isError, error, refetch } = useEmailSendSchedule();

  if (isError && !schedule) {
    return <LoadError what="the sending schedule" detail={errorMessage(error)} onRetry={() => void refetch()} />;
  }
  if (!schedule) return <SettingsCardSkeleton />;
  return <SendSchedule schedule={schedule} />;
}

function SendSchedule({ schedule }: { schedule: EmailSendSchedule }) {
  const update = useUpdateEmailSendSchedule();
  const toast = useToast();

  function toggleEnabled(enabled: boolean) {
    update.mutate(
      { enabled },
      {
        onSuccess: () =>
          toast({
            title: enabled ? "Sending schedule on" : "Sending schedule off",
            description: enabled
              ? "Cold and follow-up emails now wait for the recipient's local business hours."
              : "Cold and follow-up emails go out as soon as a run picks them up.",
          }),
        onError: (mutationError) =>
          toast({
            title: "Couldn't change the sending schedule",
            description: errorMessage(mutationError),
          }),
      },
    );
  }

  function toggleDay(row: SendScheduleRow, iso: number) {
    const on = row.days.includes(iso);
    if (on && row.days.length === 1) {
      toast({ title: "At least one send day is required" });
      return;
    }
    const days = on ? row.days.filter((day) => day !== iso) : [...row.days, iso].sort((a, b) => a - b);
    update.mutate(
      { country: row.country, days },
      {
        onSuccess: () => toast({ title: `${row.country} sends ${daysLabel(days)}` }),
        onError: (mutationError) =>
          toast({ title: `Couldn't save ${row.country}`, description: errorMessage(mutationError) }),
      },
    );
  }

  return (
    <SettingsCard
      title="Sending schedule"
      description="Only send cold and follow-up emails during each country's local business hours."
      action={
        <label className="flex cursor-pointer items-center gap-2.5 rounded-md border bg-canvas/60 py-1.5 pl-3 pr-2 text-ui text-ink-2">
          {schedule.enabled ? "On" : "Off"}
          <Switch
            checked={schedule.enabled}
            disabled={update.isPending}
            onCheckedChange={toggleEnabled}
            aria-label="Sending schedule"
          />
        </label>
      }
    >
      {schedule.rows.length === 0 ? (
        <div className="rounded-lg border border-dashed px-5 py-8 text-center">
          <p className="text-ui font-medium text-ink">No countries yet</p>
          <p className="mt-1 text-micro text-ink-3">No countries found yet among your companies.</p>
        </div>
      ) : (
        <ul className="divide-y">
          {schedule.rows.map((row) => (
            <li
              key={row.country}
              className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 py-3.5 first:pt-0 last:pb-0"
            >
              <div className="min-w-0">
                <p className="text-ui font-medium text-ink">{row.country}</p>
                <p className="mt-0.5 text-micro text-ink-3">{windowLabel(row)}</p>
              </div>
              <div className="flex items-center gap-1 rounded-full border bg-canvas/60 p-1">
                {DAYS.map((day) => {
                  const on = row.days.includes(day.iso);
                  return (
                    <button
                      key={day.iso}
                      type="button"
                      disabled={update.isPending}
                      aria-pressed={on}
                      aria-label={`${day.name} for ${row.country}`}
                      title={day.name}
                      onClick={() => toggleDay(row, day.iso)}
                      className={cn(
                        "size-7 rounded-full text-micro font-medium outline-none transition-colors",
                        "focus-visible:ring-2 focus-visible:ring-accent-500/30 disabled:cursor-not-allowed disabled:opacity-50",
                        on
                          ? "bg-accent-300 text-ink"
                          : "border border-line-strong text-ink-3 hover:text-ink-2",
                      )}
                    >
                      {day.initial}
                    </button>
                  );
                })}
              </div>
            </li>
          ))}
        </ul>
      )}
    </SettingsCard>
  );
}
