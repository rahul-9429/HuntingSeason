"use client";

import { useState } from "react";
import { SaveBar, SettingsCard, SettingsCardSkeleton } from "@/components/profile/settings-card";
import { Field, Input } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { usePreferences, useUpdatePreferences } from "@/lib/queries/profile";
import type { Preferences } from "@/lib/types";

function LakhInput({
  id,
  value,
  onChange,
}: {
  id: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ui text-ink-3">₹</span>
      <Input
        id={id}
        type="number"
        inputMode="numeric"
        min={0}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="pl-6 pr-12 font-mono tabular-nums"
      />
      <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-micro text-ink-3">
        lakh/yr
      </span>
    </div>
  );
}

export function SalaryTab() {
  const { data: preferences } = usePreferences();
  if (!preferences) return <SettingsCardSkeleton />;
  return <SalaryForm salary={preferences.salary} />;
}

function SalaryForm({ salary }: { salary: Preferences["salary"] }) {
  const [current, setCurrent] = useState(salary.current);
  const [min, setMin] = useState(salary.expectedMin);
  const [target, setTarget] = useState(salary.expectedTarget);
  const [dirty, setDirty] = useState(false);
  const update = useUpdatePreferences();
  const toast = useToast();

  function edit(setter: (value: number) => void) {
    return (value: number) => {
      setter(value);
      setDirty(true);
    };
  }

  return (
    <SettingsCard
      title="Salary expectations"
      description="Private by default. Never shared with a contact unless you include it in a message."
      footer={
        <SaveBar
          dirty={dirty}
          saving={update.isPending}
          onSave={() =>
            update.mutate(
              { salary: { current, expectedMin: min, expectedTarget: target } },
              {
                onSuccess: () => {
                  setDirty(false);
                  toast({ title: "Salary expectations saved" });
                },
              },
            )
          }
        />
      }
    >
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Current CTC" htmlFor="sal-current">
          <LakhInput id="sal-current" value={current} onChange={edit(setCurrent)} />
        </Field>
        <Field label="Minimum" htmlFor="sal-min">
          <LakhInput id="sal-min" value={min} onChange={edit(setMin)} />
        </Field>
        <Field label="Target" htmlFor="sal-target">
          <LakhInput id="sal-target" value={target} onChange={edit(setTarget)} />
        </Field>
      </div>
    </SettingsCard>
  );
}
