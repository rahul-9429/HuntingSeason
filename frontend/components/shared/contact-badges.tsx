import { Badge } from "@/components/ui/badge";
import { contactTypeLabel } from "@/lib/labels";
import type { ContactType } from "@/lib/types";

const typeTone = {
  hiring_manager: "accent",
  recruiter: "sky",
  referrer: "amber",
} as const satisfies Record<ContactType, string>;

export function ContactTypeBadge({ type, className }: { type: ContactType; className?: string }) {
  return (
    <Badge tone={typeTone[type]} className={className}>
      {contactTypeLabel[type]}
    </Badge>
  );
}
