"use client";

import { useRef, useState } from "react";
import { SaveBar, SettingsCard, SettingsCardSkeleton } from "@/components/profile/settings-card";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { useProfile, useUpdateProfile } from "@/lib/queries/profile";
import type { UserProfile } from "@/lib/types";

interface GeneralTabProps {
  title?: string;
  description?: React.ReactNode;
  onSaved?: (profile: UserProfile) => void;
}

export function GeneralTab(props: GeneralTabProps) {
  const { data: profile } = useProfile();
  if (!profile) return <SettingsCardSkeleton />;
  return <GeneralForm profile={profile} {...props} />;
}

function GeneralForm({
  profile,
  title = "General information",
  description = "Used in your signature and outreach drafts. Contacts only see what you send them.",
  onSaved,
}: GeneralTabProps & { profile: UserProfile }) {
  const [dirty, setDirty] = useState(false);
  const [shown, setShown] = useState(profile);
  const [version, setVersion] = useState(0);
  const formRef = useRef<HTMLFormElement>(null);
  const update = useUpdateProfile();
  const toast = useToast();

  if (profile !== shown && !dirty) {
    setShown(profile);
    setVersion((v) => v + 1);
  }

  function save() {
    if (!formRef.current) return;
    const patch = Object.fromEntries(new FormData(formRef.current)) as Partial<UserProfile>;
    update.mutate(patch, {
      onSuccess: (saved) => {
        setDirty(false);
        toast({ title: "Profile saved" });
        onSaved?.(saved);
      },
    });
  }

  return (
    <SettingsCard
      title={title}
      description={description}
      footer={<SaveBar dirty={dirty} saving={update.isPending} onSave={save} />}
    >
      <form
        key={version}
        ref={formRef}
        onChange={() => setDirty(true)}
        onSubmit={(e) => e.preventDefault()}
        className="grid gap-x-5 gap-y-4 sm:grid-cols-2"
      >
        <Field label="Full name" htmlFor="pf-name">
          <Input id="pf-name" name="name" defaultValue={profile.name} autoComplete="name" />
        </Field>
        <Field label="Current company" htmlFor="pf-company">
          <Input id="pf-company" name="currentCompany" defaultValue={profile.currentCompany} />
        </Field>
        <Field label="Headline" htmlFor="pf-headline" className="sm:col-span-2">
          <Input id="pf-headline" name="headline" defaultValue={profile.headline} />
        </Field>
        <Field label="Email" htmlFor="pf-email">
          <Input id="pf-email" name="email" type="email" defaultValue={profile.email} autoComplete="email" />
        </Field>
        <Field label="Phone" htmlFor="pf-phone">
          <Input id="pf-phone" name="phone" type="tel" defaultValue={profile.phone} autoComplete="tel" />
        </Field>
        <Field label="Location" htmlFor="pf-location">
          <Input id="pf-location" name="location" defaultValue={profile.location} />
        </Field>
        <Field label="Time zone" htmlFor="pf-tz">
          <Select id="pf-tz" name="timezone" defaultValue={profile.timezone}>
            <option value="">Not set</option>
            <option>IST (UTC+5:30)</option>
            <option>SGT (UTC+8:00)</option>
            <option>GST (UTC+4:00)</option>
            <option>GMT (UTC+0:00)</option>
          </Select>
        </Field>
        <Field label="LinkedIn" htmlFor="pf-linkedin">
          <Input id="pf-linkedin" name="linkedin" defaultValue={profile.linkedin} />
        </Field>
        <Field label="Portfolio" htmlFor="pf-portfolio">
          <Input id="pf-portfolio" name="portfolio" defaultValue={profile.portfolio} />
        </Field>
        <Field
          label="One-line pitch"
          htmlFor="pf-pitch"
          hint="Dropped into every outreach draft — concrete numbers beat adjectives."
          className="sm:col-span-2"
        >
          <Textarea id="pf-pitch" name="pitch" rows={2} defaultValue={profile.pitch} />
        </Field>
        <Field label="Short bio" htmlFor="pf-bio" hint="280 characters max." className="sm:col-span-2">
          <Textarea id="pf-bio" name="bio" rows={3} maxLength={280} defaultValue={profile.bio} />
        </Field>
      </form>
    </SettingsCard>
  );
}
