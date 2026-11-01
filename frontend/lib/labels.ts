import type { Channel, ContactType, Hue, MailProvider, OutreachStage, ReplyLabel } from "@/lib/types";

export const hueClasses: Record<Hue, string> = {
  slate: "bg-slate-100 text-slate-700 dark:bg-slate-400/15 dark:text-slate-300",
  blue: "bg-blue-50 text-blue-700 dark:bg-blue-400/15 dark:text-blue-300",
  indigo: "bg-indigo-50 text-indigo-700 dark:bg-indigo-400/15 dark:text-indigo-300",
  teal: "bg-teal-50 text-teal-700 dark:bg-teal-400/15 dark:text-teal-300",
  gray: "bg-gray-100 text-gray-700 dark:bg-gray-400/15 dark:text-gray-300",
  sky: "bg-sky-50 text-sky-700 dark:bg-sky-400/15 dark:text-sky-300",
};

export const contactTypeLabel: Record<ContactType, string> = {
  hiring_manager: "Hiring manager",
  recruiter: "Recruiter",
  referrer: "Referrer",
};

export const contactTypePlural: Record<ContactType, string> = {
  hiring_manager: "Hiring managers",
  recruiter: "Recruiters",
  referrer: "Referrers",
};

export const channelLabel: Record<Channel, string> = {
  email: "Email",
};

export const mailProviderLabel: Record<MailProvider, string> = {
  gmail: "Gmail",
  microsoft: "Outlook",
};

export const outreachStageLabel: Record<Exclude<OutreachStage, "new">, string> = {
  contacted: "Sent",
  hot: "Replied",
  dead: "Closed",
};

export const replyLabelText: Record<ReplyLabel, string> = {
  inquiry: "Interested",
  referral: "Pointed you elsewhere",
  not_interested: "Not interested",
  disqualified: "Asked to stop",
  neutral: "Neutral",
  bounced: "Bounced",
};
