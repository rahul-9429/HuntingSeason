"use client";

import {
  Briefcase,
  Compass,
  FileText,
  IndianRupee,
  Mail,
  Plug,
  Target,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Tabs } from "radix-ui";
import { CultureTab } from "@/components/profile/culture-tab";
import { ExperienceTab } from "@/components/profile/experience-tab";
import { GeneralTab } from "@/components/profile/general-tab";
import { IntegrationsTab } from "@/components/profile/integrations-tab";
import { OutreachTab } from "@/components/profile/outreach-tab";
import { ResumeTab } from "@/components/profile/resume-tab";
import { SalaryTab } from "@/components/profile/salary-tab";
import { TargetsTab } from "@/components/profile/targets-tab";
import { useMailbox } from "@/lib/queries/mailbox";

const TABS = [
  { value: "general", label: "General info", icon: UserRound },
  { value: "resume", label: "Résumé", icon: FileText },
  { value: "experience", label: "Experience", icon: Briefcase },
  { value: "targets", label: "Roles & locations", icon: Target },
  { value: "salary", label: "Salary", icon: IndianRupee },
  { value: "culture", label: "Work culture", icon: Compass },
  { value: "outreach", label: "Outreach emails", icon: Mail },
  { value: "integrations", label: "Integrations", icon: Plug },
] as const satisfies { value: string; label: string; icon: LucideIcon }[];

type TabValue = (typeof TABS)[number]["value"];

const isTab = (value: string | null): value is TabValue => TABS.some((t) => t.value === value);

export function ProfileTabs() {
  const searchParams = useSearchParams();
  const requested = searchParams.get("tab");
  const tab: TabValue = isTab(requested) ? requested : "general";
  const { data: mailbox } = useMailbox();
  const needsAttention = mailbox?.status === "needs_reconnect";

  return (
    <Tabs.Root
      value={tab}
      onValueChange={(value) => window.history.replaceState(null, "", `?tab=${value}`)}
      orientation="vertical"
      className="grid items-start gap-6 lg:grid-cols-[200px_minmax(0,1fr)]"
    >
      <Tabs.List
        aria-label="Profile sections"
        className="flex gap-1 overflow-x-auto [scrollbar-width:none] lg:sticky lg:top-6 lg:flex-col"
      >
        {TABS.map(({ value, label, icon: Icon }) => (
          <Tabs.Trigger
            key={value}
            value={value}
            className="group flex h-8 shrink-0 cursor-pointer items-center gap-2.5 rounded-md px-2.5 text-ui text-ink-2 outline-none transition hover:bg-sunken hover:text-ink focus-visible:ring-2 focus-visible:ring-accent-500/30 data-[state=active]:bg-surface data-[state=active]:font-medium data-[state=active]:text-ink data-[state=active]:data-[state=active]:ring-1 data-[state=active]:ring-line"
          >
            <Icon className="size-4 text-ink-3 group-data-[state=active]:text-accent-700" />
            {label}
            {value === "integrations" && needsAttention && (
              <span className="ml-auto size-1.5 rounded-full bg-amber-500" aria-label="Needs attention" />
            )}
          </Tabs.Trigger>
        ))}
      </Tabs.List>

      <div className="min-w-0">
        <Tabs.Content value="general" className="outline-none data-[state=active]:animate-enter">
          <GeneralTab />
        </Tabs.Content>
        <Tabs.Content value="resume" className="outline-none data-[state=active]:animate-enter">
          <ResumeTab />
        </Tabs.Content>
        <Tabs.Content value="experience" className="outline-none data-[state=active]:animate-enter">
          <ExperienceTab />
        </Tabs.Content>
        <Tabs.Content value="targets" className="outline-none data-[state=active]:animate-enter">
          <TargetsTab />
        </Tabs.Content>
        <Tabs.Content value="salary" className="outline-none data-[state=active]:animate-enter">
          <SalaryTab />
        </Tabs.Content>
        <Tabs.Content value="culture" className="outline-none data-[state=active]:animate-enter">
          <CultureTab />
        </Tabs.Content>
        <Tabs.Content value="outreach" className="outline-none data-[state=active]:animate-enter">
          <OutreachTab />
        </Tabs.Content>
        <Tabs.Content value="integrations" className="outline-none data-[state=active]:animate-enter">
          <IntegrationsTab />
        </Tabs.Content>
      </div>
    </Tabs.Root>
  );
}
