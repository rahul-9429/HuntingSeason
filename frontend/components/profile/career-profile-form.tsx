"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";
import { SaveBar, SettingsCard, SettingsCardSkeleton } from "@/components/profile/settings-card";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { Chip } from "@/components/ui/segmented";
import { useToast } from "@/components/ui/toast";
import { useCareerProfile, useUpdateCareerProfile } from "@/lib/queries/profile";
import type { CareerProfile, CompanySize, JobFunction, Seniority } from "@/lib/types";

const MAX_ITEMS = 10;

const SENIORITY: { value: Seniority; label: string }[] = [
  { value: "entry", label: "Entry / mid-level" },
  { value: "senior", label: "Senior / lead" },
  { value: "manager", label: "Manager" },
  { value: "head", label: "Head of" },
  { value: "director", label: "Director" },
  { value: "vp", label: "VP" },
  { value: "c_suite", label: "C-suite / founder" },
];

const FUNCTIONS: { value: JobFunction; label: string }[] = [
  { value: "engineering", label: "Engineering" },
  { value: "product", label: "Product" },
  { value: "design", label: "Design" },
  { value: "data", label: "Data" },
  { value: "sales", label: "Sales" },
  { value: "marketing", label: "Marketing" },
  { value: "customer_success", label: "Customer success" },
  { value: "finance", label: "Finance" },
  { value: "operations", label: "Operations" },
  { value: "hr", label: "People / HR" },
  { value: "legal", label: "Legal" },
  { value: "other", label: "Other" },
];

const COMPANY_SIZES: CompanySize[] = ["1,10", "11,50", "51,200", "201,500", "501,1000", "1001,5000", "5001,10000"];

const EMPTY_PROFILE: CareerProfile = {
  current_title: null,
  seniority: null,
  function: null,
  top_skills: [],
  industries: [],
  location: null,
  open_to_locations: [],
  company_size_history: [],
};

function toggle<T>(list: T[], item: T) {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}

function TagList({
  label,
  values,
  placeholder,
  onChange,
}: {
  label: string;
  values: string[];
  placeholder: string;
  onChange: (values: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  function add() {
    const value = draft.trim();
    if (!value || values.some((v) => v.toLowerCase() === value.toLowerCase())) return;
    onChange([...values, value]);
    setDraft("");
  }

  return (
    <div>
      <p className="text-micro font-medium text-ink-2">{label}</p>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {values.map((value) => (
          <span
            key={value}
            className="inline-flex h-7 items-center gap-1 rounded-full border bg-canvas/60 pl-3 pr-1 text-ui text-ink"
          >
            {value}
            <button
              type="button"
              onClick={() => onChange(values.filter((v) => v !== value))}
              aria-label={`Remove ${value}`}
              className="grid size-5 cursor-pointer place-items-center rounded-full text-ink-3 hover:bg-sunken hover:text-ink"
            >
              <X className="size-3" />
            </button>
          </span>
        ))}
        {values.length < MAX_ITEMS && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              add();
            }}
            className="flex items-center gap-1"
          >
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={100}
              placeholder={placeholder}
              aria-label={label}
              className="h-7 w-40 rounded-full"
            />
            <Button type="submit" size="icon-sm" variant="ghost" aria-label={`Add to ${label}`} disabled={!draft.trim()}>
              <Plus />
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}

interface CareerProfileCardProps {
  title?: string;
  description?: React.ReactNode;
  onSaved?: (profile: CareerProfile) => void;
}

/** Loads the career profile and renders the editable form for it. */
export function CareerProfileCard(props: CareerProfileCardProps) {
  const { data: profile, isPending } = useCareerProfile();
  if (isPending) return <SettingsCardSkeleton />;
  return <CareerProfileForm profile={profile ?? EMPTY_PROFILE} {...props} />;
}

function CareerProfileForm({
  profile,
  title = "Search profile",
  description = "Read from your résumé. Company search uses it to fill in whatever your search leaves open.",
  onSaved,
}: CareerProfileCardProps & { profile: CareerProfile }) {
  const [draft, setDraft] = useState(profile);
  const [shown, setShown] = useState(profile);
  const [dirty, setDirty] = useState(false);
  const update = useUpdateCareerProfile();
  const toast = useToast();

  function set<K extends keyof CareerProfile>(key: K, value: CareerProfile[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setDirty(true);
  }

  // A newly read résumé (or a refetch) replaces the profile: show it, unless
  // the user has unsaved edits
  if (profile !== shown && !dirty) {
    setShown(profile);
    setDraft(profile);
  }

  const text = (value: string) => value.trim() || null;

  return (
    <SettingsCard
      title={title}
      description={description}
      footer={
        <SaveBar
          dirty={dirty}
          saving={update.isPending}
          onSave={() =>
            update.mutate(
              { ...draft, current_title: text(draft.current_title ?? ""), location: text(draft.location ?? "") },
              {
                onSuccess: (saved) => {
                  setDirty(false);
                  toast({ title: "Search profile saved" });
                  onSaved?.(saved);
                },
              },
            )
          }
        />
      }
    >
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Current title" htmlFor="cp-title">
            <Input
              id="cp-title"
              maxLength={100}
              value={draft.current_title ?? ""}
              onChange={(e) => set("current_title", e.target.value)}
              placeholder="e.g. Senior Backend Engineer"
            />
          </Field>
          <Field label="Based in" htmlFor="cp-location">
            <Input
              id="cp-location"
              maxLength={100}
              value={draft.location ?? ""}
              onChange={(e) => set("location", e.target.value)}
              placeholder="e.g. Bengaluru, India"
            />
          </Field>
          <Field label="Seniority" htmlFor="cp-seniority">
            <Select
              id="cp-seniority"
              value={draft.seniority ?? ""}
              onChange={(e) => set("seniority", (e.target.value || null) as Seniority | null)}
            >
              <option value="">Not set</option>
              {SENIORITY.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Function" htmlFor="cp-function">
            <Select
              id="cp-function"
              value={draft.function ?? ""}
              onChange={(e) => set("function", (e.target.value || null) as JobFunction | null)}
            >
              <option value="">Not set</option>
              {FUNCTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <TagList
          label="Top skills"
          values={draft.top_skills}
          placeholder="Add a skill…"
          onChange={(values) => set("top_skills", values)}
        />
        <TagList
          label="Industries"
          values={draft.industries}
          placeholder="Add an industry…"
          onChange={(values) => set("industries", values)}
        />
        <TagList
          label="Open to working in"
          values={draft.open_to_locations}
          placeholder="Add a place…"
          onChange={(values) => set("open_to_locations", values)}
        />

        <div>
          <div className="flex flex-wrap items-center justify-between gap-x-4">
            <p className="text-micro font-medium text-ink-2">Company sizes you&apos;ve worked at</p>
            <span className="text-micro text-ink-3">Employees</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {COMPANY_SIZES.map((size) => (
              <Chip
                key={size}
                pressed={draft.company_size_history.includes(size)}
                onPressedChange={() => set("company_size_history", toggle(draft.company_size_history, size))}
              >
                {size.replace(",", "–")}
              </Chip>
            ))}
          </div>
        </div>
      </div>
    </SettingsCard>
  );
}
