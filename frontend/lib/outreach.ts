import type { ContactType, ContactWithCompany, UserProfile } from "@/lib/types";
import { firstName } from "@/lib/utils";

const asks: Record<ContactType, string> = {
  hiring_manager: "Would you be open to a 15-minute call next week to see if there's a fit?",
  recruiter: "Could we set up a quick call to see whether my background fits what the team needs?",
  referrer:
    "Would you be comfortable referring me, or pointing me to the right person? I'm happy to send a short blurb to make it easy.",
};

const openers: Record<ContactType, string> = {
  hiring_manager: "I'd like to be considered for the work your team is doing",
  recruiter: "I'm looking at roles on your team and would like to be considered",
  referrer: "I'm trying to get in front of the right person on your team",
};

export function buildDraft(contact: ContactWithCompany, user: UserProfile) {
  const company = contact.company.name;
  const pitch = user.pitch.trim().replace(/\.$/, "");
  const opener = contact.hook
    ? `I ${contact.hook}, and ${openers[contact.type]}.`
    : `${openers[contact.type]} at ${company}.`;
  return {
    subject: `Interested in joining ${company}`,
    body: [
      `Hi ${firstName(contact.name)},`,
      opener,
      pitch && `${pitch}. I think that lines up closely with what you're building.`,
      asks[contact.type],
      `Best,\n${firstName(user.name)}`,
    ]
      .filter(Boolean)
      .join("\n\n"),
  };
}
