import type { Metadata } from "next";
import { Suspense } from "react";
import { ProfileTabs } from "@/components/profile/profile-tabs";
import { PageHeader } from "@/components/shell/page-header";

export const metadata: Metadata = { title: "Profile" };

export default function ProfilePage() {
  return (
    <div className="scrollbar-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-[1120px] px-5 py-8 sm:px-8 lg:px-10 lg:py-10">
        <PageHeader
          eyebrow="Profile & preferences"
          title={
            <>
              How Auto-Hunt <em className="text-accent-700">sees you.</em>
            </>
          }
          description="Everything here shapes who we find and how your drafts read. Nothing is shared with a contact until you send a message."
        />

        <Suspense fallback={<div className="h-96 animate-pulse rounded-xl border-2 border-line-strong bg-surface/60" />}>
          <ProfileTabs />
        </Suspense>
      </div>
    </div>
  );
}
