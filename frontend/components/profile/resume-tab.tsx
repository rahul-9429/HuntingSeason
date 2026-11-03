"use client";

import { ResumeCard } from "@/components/contacts/resume-card";
import { CareerProfileCard } from "@/components/profile/career-profile-form";

export function ResumeTab() {
  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <CareerProfileCard />
      <ResumeCard />
    </div>
  );
}
