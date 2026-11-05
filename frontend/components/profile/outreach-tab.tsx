"use client";

import { Eye, LoaderCircle, Plus, Star, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { SendScheduleCard } from "@/components/profile/send-schedule-card";
import { SaveBar, SettingsCard, SettingsCardSkeleton } from "@/components/profile/settings-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/api/client";
import { htmlToText, textToHtml } from "@/lib/email-text";
import { useContactPicker } from "@/lib/queries/contacts";
import { useMailbox } from "@/lib/queries/mailbox";
import {
  useDeleteTemplate,
  useOutreachPreview,
  useOutreachSettings,
  useSaveTemplate,
  useTemplates,
  useUpdateOutreachSettings,
} from "@/lib/queries/outreach";
import type { EmailTemplate, OutreachSettings, Writer } from "@/lib/types";

const WRITERS: { value: Writer; label: string; description: string }[] = [
  {
    value: "email_agent",
    label: "Write with AI",
    description:
      "The email agent writes each email from scratch from your résumé and the person's role and company. No template needed.",
  },
  {
    value: "template",
    label: "Your template",
    description: "Starts from your default template and adjusts it to each person, keeping your links.",
  },
];

const STARTER = {
  name: "First email",
  subject: "[[Interested in|Curious about]] {role} roles at {company_name}",
  body: [
    "Hi {contact_name},",
    "[[I saw|I noticed]] that {company_name} is hiring for {role}, and I'd like to be considered. The problems your team works on line up closely with what I've been building for the last few years.",
    "Would you be open to a [[short|quick]] 15-minute call this week, or could you point me to the right person?",
  ].join("\n\n"),
};

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function OutreachTab() {
  return (
    <div className="space-y-4">
      <WritingCard />
      <SendScheduleCard />
      <TemplatesCard />
      <PreviewCard />
    </div>
  );
}

interface WritingForm {
  writer: Writer;
  writerInstructions: string;
  maxFollowUps: number;
  followUpDays: string;
  senderName: string;
  signature: string;
  bookingLink: string;
  replyFacts: string;
  replyCc: string;
}

function toForm(settings: OutreachSettings): WritingForm {
  return {
    writer: settings.writer,
    writerInstructions: settings.writer_instructions ?? "",
    maxFollowUps: settings.max_follow_ups,
    followUpDays: String(settings.follow_up_interval_days),
    senderName: settings.sender_name ?? "",
    signature: settings.signature_html ? htmlToText(settings.signature_html) : "",
    bookingLink: settings.reply_booking_link ?? "",
    replyFacts: settings.reply_facts ?? "",
    replyCc: settings.reply_cc.join(", "),
  };
}

const addresses = (value: string) => value.split(/[\s,;]+/).filter(Boolean);

function WritingCard() {
  const { data: settings } = useOutreachSettings();
  if (!settings) return <SettingsCardSkeleton />;
  return <WritingSettings settings={settings} />;
}

function WritingSettings({ settings }: { settings: OutreachSettings }) {
  const [form, setForm] = useState(() => toForm(settings));
  const [shown, setShown] = useState(settings);
  const [dirty, setDirty] = useState(false);
  const { data: templates } = useTemplates();
  const { data: mailbox } = useMailbox();
  const update = useUpdateOutreachSettings();
  const toast = useToast();

  if (settings !== shown && !dirty) {
    setShown(settings);
    setForm(toForm(settings));
  }

  function set<K extends keyof WritingForm>(key: K, value: WritingForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setDirty(true);
  }

  const badLink = form.bookingLink.trim() !== "" && !/^https?:\/\/\S+$/.test(form.bookingLink.trim());
  const badCc = addresses(form.replyCc).some((address) => !EMAIL.test(address));
  const days = Number(form.followUpDays);
  const badDays = !/^\d+$/.test(form.followUpDays.trim()) || days < 1 || days > 30;
  const noDefault = form.writer === "template" && templates !== undefined && !templates.some((t) => t.is_default);
  const text = (value: string) => value.trim() || null;

  function save() {
    if (badLink || badCc || badDays) {
      toast({ title: "Fix the highlighted fields first" });
      return;
    }
    update.mutate(
      {
        writer: form.writer,
        writer_instructions: text(form.writerInstructions),
        max_follow_ups: form.maxFollowUps,
        follow_up_interval_days: days,
        sender_name: text(form.senderName),
        signature_html: form.signature.trim() ? textToHtml(form.signature) : null,
        reply_booking_link: text(form.bookingLink),
        reply_facts: text(form.replyFacts),
        reply_cc: addresses(form.replyCc),
      },
      {
        onSuccess: () => {
          setDirty(false);
          toast({ title: "Outreach settings saved" });
        },
      },
    );
  }

  return (
    <SettingsCard
      title="How your emails are written"
      description="Used for first emails, follow-ups and drafted replies. Turn outreach on or off in Integrations."
      footer={<SaveBar dirty={dirty} saving={update.isPending} onSave={save} />}
    >
      <div className="space-y-6">
        <div>
          <p className="text-micro font-medium text-ink-2">Who writes the first email</p>
          <Segmented
            aria-label="Writer"
            value={form.writer}
            onValueChange={(value) => set("writer", value)}
            options={WRITERS.map(({ value, label }) => ({ value, label }))}
            className="mt-2"
          />
          <p className="mt-1.5 text-micro text-ink-3">{WRITERS.find((w) => w.value === form.writer)?.description}</p>
          {noDefault && (
            <p className="mt-2 flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-micro text-amber-900 ring-1 ring-inset ring-amber-200/70 dark:bg-amber-400/10 dark:text-amber-200 dark:ring-amber-400/20">
              <TriangleAlert className="mt-px size-3.5 shrink-0" />
              Add a default template below, or nothing gets sent with this writer.
            </p>
          )}
          {form.writer === "email_agent" && (
            <Field
              label="Anything the email agent should know"
              htmlFor="ot-instructions"
              hint="Tone, what to mention, what to avoid. Optional."
              className="mt-4"
            >
              <Textarea
                id="ot-instructions"
                rows={3}
                maxLength={4000}
                value={form.writerInstructions}
                onChange={(e) => set("writerInstructions", e.target.value)}
                placeholder="e.g. Keep it under 100 words and mention my open-source work."
              />
            </Field>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Follow-ups" htmlFor="ot-follow-ups" hint="Sent in the same thread until they reply.">
            <Select
              id="ot-follow-ups"
              value={form.maxFollowUps}
              onChange={(e) => set("maxFollowUps", Number(e.target.value))}
            >
              {[0, 1, 2, 3, 4, 5].map((count) => (
                <option key={count} value={count}>
                  {count === 0 ? "None" : count === 1 ? "1 follow-up" : `${count} follow-ups`}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Days between emails" htmlFor="ot-days" hint={badDays ? "Pick 1 to 30 days." : undefined}>
            <Input
              id="ot-days"
              type="number"
              min={1}
              max={30}
              value={form.followUpDays}
              onChange={(e) => set("followUpDays", e.target.value)}
              aria-invalid={badDays}
            />
          </Field>
          <Field label="Sender name" htmlFor="ot-sender" hint="Who the email says it's from.">
            <Input
              id="ot-sender"
              maxLength={200}
              value={form.senderName}
              onChange={(e) => set("senderName", e.target.value)}
              placeholder={mailbox?.from_name ?? "Your name"}
            />
          </Field>
          <Field
            label="Signature"
            htmlFor="ot-signature"
            hint="Added under every email. Empty signs off with your first name."
          >
            <Textarea
              id="ot-signature"
              rows={3}
              value={form.signature}
              onChange={(e) => set("signature", e.target.value)}
              placeholder={"Rahul Kumar\nSenior Backend Engineer · linkedin.com/in/you"}
            />
          </Field>
        </div>

        <div className="border-t pt-5">
          <p className="text-ui font-medium text-ink">Drafted replies</p>
          <p className="mt-0.5 text-micro text-ink-3">
            When someone answers with interest, a reply is drafted for you in the inbox.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label="Booking link" htmlFor="ot-booking" hint={badLink ? "Use a full https:// link." : undefined}>
              <Input
                id="ot-booking"
                value={form.bookingLink}
                onChange={(e) => set("bookingLink", e.target.value)}
                placeholder="https://cal.com/you/15min"
                aria-invalid={badLink}
              />
            </Field>
            <Field
              label="Copy these addresses"
              htmlFor="ot-cc"
              hint={badCc ? "One of these isn't an email address." : "Comma separated. Optional."}
            >
              <Input
                id="ot-cc"
                value={form.replyCc}
                onChange={(e) => set("replyCc", e.target.value)}
                placeholder="you+replies@gmail.com"
                aria-invalid={badCc}
              />
            </Field>
            <Field
              label="Facts the drafts can use"
              htmlFor="ot-facts"
              hint="Notice period, visa, availability, salary range. Only these get mentioned."
              className="sm:col-span-2"
            >
              <Textarea
                id="ot-facts"
                rows={3}
                maxLength={4000}
                value={form.replyFacts}
                onChange={(e) => set("replyFacts", e.target.value)}
                placeholder="30-day notice period. Open to relocating to Dubai. Free most afternoons IST."
              />
            </Field>
          </div>
        </div>
      </div>
    </SettingsCard>
  );
}

function TemplatesCard() {
  const { data: templates } = useTemplates();
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [confirming, setConfirming] = useState<number | null>(null);
  const save = useSaveTemplate();
  const remove = useDeleteTemplate();
  const toast = useToast();

  if (!templates) return <SettingsCardSkeleton />;
  const editingTemplate = templates.find((t) => t.id === editing);

  return (
    <SettingsCard
      title="Templates"
      description={
        <>
          The template writer starts from your default. Use {"{contact_name}"}, {"{company_name}"} and {"{role}"};
          [[Hi|Hello]] picks one at random.
        </>
      }
      action={
        editing === null && (
          <Button size="sm" onClick={() => setEditing("new")}>
            <Plus /> New template
          </Button>
        )
      }
    >
      {editing !== null ? (
        <TemplateForm
          key={editing}
          template={editingTemplate}
          first={templates.length === 0}
          onDone={() => setEditing(null)}
        />
      ) : templates.length === 0 ? (
        <div className="rounded-lg border border-dashed px-5 py-8 text-center">
          <p className="text-ui font-medium text-ink">No templates yet</p>
          <p className="mt-1 text-micro text-ink-3">Start from an example and make it yours.</p>
          <Button size="sm" variant="primary" className="mt-3" onClick={() => setEditing("new")}>
            <Plus /> Create your first template
          </Button>
        </div>
      ) : (
        <ul className="divide-y">
          {templates.map((template) => (
            <li key={template.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 first:pt-0 last:pb-0">
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-ui font-medium text-ink">
                  {template.name}
                  {template.is_default && <Badge tone="accent">Default</Badge>}
                  {template.skip_ai && <Badge tone="outline">Sent as written</Badge>}
                </p>
                <p className="truncate text-micro text-ink-3">{template.subject}</p>
              </div>
              <div className="flex items-center gap-1">
                {!template.is_default && (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={save.isPending}
                    onClick={() =>
                      save.mutate(
                        { id: template.id, is_default: true },
                        { onSuccess: () => toast({ title: `“${template.name}” is now your default` }) },
                      )
                    }
                  >
                    <Star /> Make default
                  </Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => setEditing(template.id)}>
                  Edit
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={remove.isPending}
                  onBlur={() => setConfirming(null)}
                  onClick={() => {
                    if (confirming === template.id) {
                      remove.mutate(template.id, { onSuccess: () => toast({ title: "Template deleted" }) });
                    } else {
                      setConfirming(template.id);
                    }
                  }}
                  className={confirming === template.id ? "text-rose-700 dark:text-rose-300" : undefined}
                >
                  {confirming === template.id ? "Delete for good?" : "Delete"}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </SettingsCard>
  );
}

function TemplateForm({
  template,
  first,
  onDone,
}: {
  template: EmailTemplate | undefined;
  first: boolean;
  onDone: () => void;
}) {
  const [name, setName] = useState(template?.name ?? (first ? STARTER.name : ""));
  const [subject, setSubject] = useState(template?.subject ?? (first ? STARTER.subject : ""));
  const [body, setBody] = useState(template ? htmlToText(template.body_html) : first ? STARTER.body : "");
  const [skipAi, setSkipAi] = useState(template?.skip_ai ?? false);
  const save = useSaveTemplate();
  const toast = useToast();
  const ready = Boolean(name.trim() && subject.trim() && body.trim());

  function submit() {
    save.mutate(
      {
        id: template?.id,
        name: name.trim(),
        subject: subject.trim(),
        body_html: textToHtml(body),
        skip_ai: skipAi,
        ...(template ? {} : { is_default: first }),
      },
      {
        onSuccess: () => {
          toast({ title: template ? "Template saved" : "Template created" });
          onDone();
        },
      },
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) submit();
      }}
      className="space-y-4"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" htmlFor="tpl-name">
          <Input id="tpl-name" maxLength={200} value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Subject" htmlFor="tpl-subject">
          <Input id="tpl-subject" maxLength={998} value={subject} onChange={(e) => setSubject(e.target.value)} />
        </Field>
      </div>
      <Field label="Email" htmlFor="tpl-body" hint="Links: [text](https://…) or paste the URL. Your signature is added below.">
        <Textarea
          id="tpl-body"
          rows={10}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          className="font-mono text-micro leading-5"
        />
      </Field>
      <label className="flex cursor-pointer items-center justify-between gap-4 rounded-lg border px-3 py-2.5">
        <span>
          <span className="block text-ui text-ink">Send exactly as written</span>
          <span className="block text-micro text-ink-3">
            Off: AI adjusts each email to the person and company, keeping your links and wording close.
          </span>
        </span>
        <Switch checked={skipAi} onCheckedChange={setSkipAi} aria-label="Send exactly as written" />
      </label>
      <div className="flex justify-end gap-2">
        <Button size="sm" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
        <Button size="sm" variant="primary" type="submit" disabled={!ready || save.isPending}>
          {save.isPending && <LoaderCircle className="animate-spin" />}
          {template ? "Save template" : "Create template"}
        </Button>
      </div>
    </form>
  );
}

function PreviewCard() {
  const { data: contacts } = useContactPicker();
  const { data: templates } = useTemplates();
  const { data: settings } = useOutreachSettings();
  const { data: mailbox } = useMailbox();
  const [contactId, setContactId] = useState("");
  const [writer, setWriter] = useState<Writer | null>(null);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [requested, setRequested] = useState<{ contactId: string; writer: Writer; templateId?: number } | null>(
    null,
  );
  const preview = useOutreachPreview(requested?.contactId ?? null, {
    writer: requested?.writer,
    templateId: requested?.templateId,
  });

  const withEmail = contacts?.items.filter((c) => c.email) ?? [];
  const chosenWriter = writer ?? settings?.writer ?? "email_agent";
  const chosenContact = contactId || withEmail[0]?.id || "";
  const chosenTemplate = templateId ?? templates?.find((t) => t.is_default)?.id;

  function runPreview() {
    const next = {
      contactId: chosenContact,
      writer: chosenWriter,
      templateId: chosenWriter === "template" ? chosenTemplate : undefined,
    };
    const same =
      requested?.contactId === next.contactId &&
      requested.writer === next.writer &&
      requested.templateId === next.templateId;
    if (same) void preview.refetch();
    else setRequested(next);
  }

  let blocked: React.ReactNode = null;
  if (mailbox === null) {
    blocked = (
      <>
        <Link href="/profile?tab=integrations" className="font-medium text-accent-700 hover:text-accent-800">
          Connect your email
        </Link>{" "}
        to preview.
      </>
    );
  } else if (contacts && withEmail.length === 0) {
    blocked = (
      <>
        Add people from{" "}
        <Link href="/companies" className="font-medium text-accent-700 hover:text-accent-800">
          Companies
        </Link>{" "}
        to preview an email to them.
      </>
    );
  } else if (chosenWriter === "template" && templates !== undefined && chosenTemplate === undefined) {
    blocked = "Make one of your templates the default first, or nothing gets sent with this writer.";
  }

  return (
    <SettingsCard
      title="Preview"
      description="See exactly what one of your contacts would get. Nothing is sent."
    >
      {blocked ? (
        <p className="text-ui text-ink-2">{blocked}</p>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto]">
            <Field label="To" htmlFor="pv-contact">
              <Select id="pv-contact" value={chosenContact} onChange={(e) => setContactId(e.target.value)}>
                {withEmail.map((contact) => (
                  <option key={contact.id} value={contact.id}>
                    {contact.name} · {contact.title} at {contact.company.name}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="flex flex-col gap-1.5">
              <span className="text-micro font-medium text-ink-2">Writer</span>
              <Segmented
                aria-label="Preview writer"
                value={chosenWriter}
                onValueChange={setWriter}
                options={WRITERS.map(({ value, label }) => ({ value, label }))}
              />
            </div>
          </div>
          {chosenWriter === "template" && templates && templates.length > 1 && (
            <Field label="Template" htmlFor="pv-template">
              <Select
                id="pv-template"
                value={chosenTemplate}
                onChange={(e) => setTemplateId(Number(e.target.value))}
              >
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                    {template.is_default ? " (default)" : ""}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          <Button
            size="sm"
            variant="primary"
            disabled={!chosenContact || preview.isFetching}
            onClick={runPreview}
          >
            {preview.isFetching ? <LoaderCircle className="animate-spin" /> : <Eye />}
            {preview.isFetching ? "Writing…" : "Preview email"}
          </Button>

          {requested && preview.isError && (
            <p className="text-ui text-rose-700 dark:text-rose-300">{errorMessage(preview.error)}</p>
          )}
          {requested && preview.data && !preview.isFetching && (
            <div className="rounded-lg border bg-canvas/50">
              <p className="border-b px-4 py-2.5 text-ui font-medium text-ink">{preview.data.subject}</p>
              <p className="whitespace-pre-line px-4 py-3 text-ui leading-6 text-ink-2">
                {htmlToText(preview.data.html)}
              </p>
            </div>
          )}
        </div>
      )}
    </SettingsCard>
  );
}
