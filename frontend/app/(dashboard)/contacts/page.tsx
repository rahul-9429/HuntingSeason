import type { Metadata } from "next";
import { ContactFeed } from "@/components/contacts/contact-feed";
import { OutreachBanner } from "@/components/contacts/outreach-banner";
import { ResumeCard } from "@/components/contacts/resume-card";
import { PageHeader } from "@/components/shell/page-header";

export const metadata: Metadata = { title: "Contacts" };

export default function ContactsPage() {
  return (
    <div className="scrollbar-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-[1240px] px-5 py-8 sm:px-8 lg:px-10 lg:py-10">
        <PageHeader
          eyebrow="Contacts · Auto-Hunt"
          title={
            <>
              People who can <em className="text-accent-700">get you in.</em>
            </>
          }
          description="Hiring managers, recruiters and would-be referrers matched to your résumé and target roles, ranked by match score."
        />

        <OutreachBanner />

        <div className="mt-10 grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
          <ContactFeed />
          <aside>
            <ResumeCard />
          </aside>
        </div>
      </div>
    </div>
  );
}
