"use client";

import { Globe, Laptop, MapPin, Plus, X } from "lucide-react";
import { useState } from "react";
import { HuntCard } from "@/components/profile/hunt-card";
import { SaveBar, SettingsCard, SettingsCardSkeleton } from "@/components/profile/settings-card";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/field";
import { Chip, Segmented } from "@/components/ui/segmented";
import { useToast } from "@/components/ui/toast";
import { locationLabel, locationOptions, sameLocation } from "@/lib/data/locations";
import { usePreferences, useUpdatePreferences } from "@/lib/queries/profile";
import type { Preferences, TargetLocation } from "@/lib/types";

const SENIORITY = ["Mid", "Senior", "Staff", "Principal"];

function toggle<T>(list: T[], item: T) {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}

export function TargetsTab() {
  const { data: preferences } = usePreferences();
  return (
    <div className="space-y-4">
      <HuntCard />
      {preferences ? <TargetsForm targets={preferences} /> : <SettingsCardSkeleton />}
    </div>
  );
}

function TargetsForm({ targets }: { targets: Preferences }) {
  const [roles, setRoles] = useState(targets.roles);
  const [roleDraft, setRoleDraft] = useState("");
  const [seniority, setSeniority] = useState(targets.seniority);
  const [locations, setLocations] = useState(targets.locations);
  const [remote, setRemote] = useState(targets.remote);
  const [country, setCountry] = useState(locationOptions[0]!.country);
  const [city, setCity] = useState("");
  const [dirty, setDirty] = useState(false);
  const update = useUpdatePreferences();
  const toast = useToast();

  function edit<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value);
      setDirty(true);
    };
  }

  function addRole() {
    const role = roleDraft.trim();
    if (!role || roles.includes(role)) return;
    edit(setRoles)([...roles, role]);
    setRoleDraft("");
  }

  const cityOptions = locationOptions.find((o) => o.country === country)?.cities ?? [];

  function addLocation() {
    const location: TargetLocation = city ? { country, city } : { country };
    if (locations.some((l) => sameLocation(l, location))) {
      toast({ title: `${locationLabel(location)} is already a target` });
      return;
    }
    edit(setLocations)([...locations, location]);
    setCity("");
  }

  return (
    <SettingsCard
      title="Roles & locations"
      description="Auto-Hunt looks for people who hire for these roles, in these places."
      footer={
        <SaveBar
          dirty={dirty}
          saving={update.isPending}
          onSave={() =>
            update.mutate(
              { roles, seniority, locations, remote },
              {
                onSuccess: () => {
                  setDirty(false);
                  toast({ title: "Targets saved" });
                },
              },
            )
          }
        />
      }
    >
      <div className="space-y-6">
        <div>
          <p className="text-micro font-medium text-ink-2">Target roles</p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {roles.map((role) => (
              <span
                key={role}
                className="inline-flex h-7 items-center gap-1 rounded-full border bg-canvas/60 pl-3 pr-1 text-ui text-ink"
              >
                {role}
                <button
                  type="button"
                  onClick={() => edit(setRoles)(roles.filter((r) => r !== role))}
                  aria-label={`Remove ${role}`}
                  className="grid size-5 cursor-pointer place-items-center rounded-full text-ink-3 hover:bg-sunken hover:text-ink"
                >
                  <X className="size-3" />
                </button>
              </span>
            ))}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                addRole();
              }}
              className="flex items-center gap-1"
            >
              <Input
                value={roleDraft}
                onChange={(e) => setRoleDraft(e.target.value)}
                placeholder="Add a role…"
                aria-label="Add a target role"
                className="h-7 w-40 rounded-full"
              />
              <Button type="submit" size="icon-sm" variant="ghost" aria-label="Add role" disabled={!roleDraft.trim()}>
                <Plus />
              </Button>
            </form>
          </div>
        </div>

        <div>
          <p className="text-micro font-medium text-ink-2">Seniority</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {SENIORITY.map((level) => (
              <Chip
                key={level}
                pressed={seniority.includes(level)}
                onPressedChange={() => edit(setSeniority)(toggle(seniority, level))}
              >
                {level}
              </Chip>
            ))}
          </div>
        </div>

        <div>
          <div className="flex flex-wrap items-center justify-between gap-x-4">
            <p className="text-micro font-medium text-ink-2">Target locations</p>
            <span className="text-micro text-ink-3">A specific city, or anywhere in a country</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {locations.map((location) => {
              const Icon = location.city ? MapPin : Globe;
              const label = locationLabel(location);
              return (
                <span
                  key={label}
                  className="inline-flex h-7 items-center gap-1.5 rounded-full border bg-canvas/60 pl-2.5 pr-1 text-ui text-ink"
                >
                  <Icon className="size-3.5 text-ink-3" />
                  {label}
                  <button
                    type="button"
                    onClick={() => edit(setLocations)(locations.filter((l) => !sameLocation(l, location)))}
                    aria-label={`Remove ${label}`}
                    className="grid size-5 cursor-pointer place-items-center rounded-full text-ink-3 hover:bg-sunken hover:text-ink"
                  >
                    <X className="size-3" />
                  </button>
                </span>
              );
            })}
            {locations.length === 0 && (
              <span className="text-micro text-ink-3">No locations yet — Auto-Hunt will only use your remote setting.</span>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Select
              aria-label="Country"
              value={country}
              onChange={(e) => {
                setCountry(e.target.value);
                setCity("");
              }}
              className="w-auto min-w-44"
            >
              {locationOptions.map((option) => (
                <option key={option.country} value={option.country}>
                  {option.country}
                </option>
              ))}
            </Select>
            <Select
              aria-label="City"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              disabled={cityOptions.length === 0}
              className="w-auto min-w-48"
            >
              <option value="">Anywhere in {country}</option>
              {cityOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
            <Button size="sm" onClick={addLocation}>
              <Plus /> Add location
            </Button>
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-canvas/50 px-3.5 py-3">
            <div className="flex items-start gap-2.5">
              <Laptop className="mt-0.5 size-4 text-ink-3" />
              <div>
                <p className="text-ui font-medium text-ink">Open to remote</p>
                <p className="text-micro text-ink-3">Also include remote roles hiring from this region.</p>
              </div>
            </div>
            <Segmented
              aria-label="Remote preference"
              value={remote}
              onValueChange={edit(setRemote)}
              options={[
                { value: "none", label: "No" },
                { value: "country", label: "India only" },
                { value: "apac", label: "APAC" },
                { value: "global", label: "Worldwide" },
              ]}
            />
          </div>
        </div>
      </div>
    </SettingsCard>
  );
}
