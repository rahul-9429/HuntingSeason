"use client";

import { useState } from "react";
import { SaveBar, SettingRow, SettingsCard, SettingsCardSkeleton } from "@/components/profile/settings-card";
import { Chip, Segmented } from "@/components/ui/segmented";
import { useToast } from "@/components/ui/toast";
import { usePreferences, useUpdatePreferences } from "@/lib/queries/profile";
import type { Preferences } from "@/lib/types";

const WORK_MODES = ["Remote", "Hybrid", "Onsite"];
const STAGES = ["Seed – Series A", "Growth (Series B–D)", "Public"];

function toggle(list: string[], item: string) {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}

export function CultureTab() {
  const { data: preferences } = usePreferences();
  if (!preferences) return <SettingsCardSkeleton />;
  return <CultureForm culture={preferences.culture} />;
}

function CultureForm({ culture }: { culture: Preferences["culture"] }) {
  const [modes, setModes] = useState(culture.workModes);
  const [stages, setStages] = useState(culture.companyStage);
  const [teamSize, setTeamSize] = useState(culture.teamSize);
  const [pace, setPace] = useState(culture.pace);
  const [dirty, setDirty] = useState(false);
  const update = useUpdatePreferences();
  const toast = useToast();

  function edit<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value);
      setDirty(true);
    };
  }

  return (
    <SettingsCard
      title="Work culture"
      description="Auto-Hunt ranks contacts lower when the company is outside the stages you pick."
      footer={
        <SaveBar
          dirty={dirty}
          saving={update.isPending}
          onSave={() =>
            update.mutate(
              { culture: { workModes: modes, companyStage: stages, teamSize, pace } },
              {
                onSuccess: () => {
                  setDirty(false);
                  toast({ title: "Culture preferences saved" });
                },
              },
            )
          }
        />
      }
    >
      <div className="divide-y">
        <SettingRow label="Work mode">
          <div className="flex flex-wrap gap-1.5">
            {WORK_MODES.map((mode) => (
              <Chip key={mode} pressed={modes.includes(mode)} onPressedChange={() => edit(setModes)(toggle(modes, mode))}>
                {mode}
              </Chip>
            ))}
          </div>
        </SettingRow>
        <SettingRow label="Company stage">
          <div className="flex flex-wrap gap-1.5">
            {STAGES.map((stage) => (
              <Chip key={stage} pressed={stages.includes(stage)} onPressedChange={() => edit(setStages)(toggle(stages, stage))}>
                {stage}
              </Chip>
            ))}
          </div>
        </SettingRow>
        <SettingRow label="Team size">
          <Segmented
            aria-label="Team size"
            value={teamSize}
            onValueChange={edit(setTeamSize)}
            options={[
              { value: "small", label: "5–10" },
              { value: "mid", label: "10–30" },
              { value: "large", label: "30+" },
            ]}
          />
        </SettingRow>
        <SettingRow label="Pace">
          <Segmented
            aria-label="Pace"
            value={pace}
            onValueChange={edit(setPace)}
            options={[
              { value: "steady", label: "Steady" },
              { value: "balanced", label: "Balanced" },
              { value: "fast", label: "Fast-moving" },
            ]}
          />
        </SettingRow>
      </div>
    </SettingsCard>
  );
}
