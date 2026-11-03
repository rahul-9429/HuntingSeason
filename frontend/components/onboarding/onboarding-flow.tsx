"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ResumeCard } from "@/components/contacts/resume-card";
import { CareerProfileCard } from "@/components/profile/career-profile-form";
import { GeneralTab } from "@/components/profile/general-tab";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { AFTER_AUTH_URL } from "@/lib/auth";
import { useCareerProfile } from "@/lib/queries/profile";

const SEARCH_URL = "/companies";
const STEPS = ["upload", "about", "review"] as const;

function BrandMark() {
  return (
    <span className="flex items-center gap-2.5">
      <span
        aria-hidden
        className="grid size-6 place-items-center rounded-md bg-ink pb-px font-serif text-[17px] italic leading-none text-on-ink"
      >
        j
      </span>
      <span className="text-[15px] font-semibold tracking-tight text-ink">Hunting Season</span>
    </span>
  );
}

export function OnboardingFlow() {
  const [step, setStep] = useState<(typeof STEPS)[number]>("upload");
  const { data: profile } = useCareerProfile();
  const router = useRouter();

  return (
    <div className="mx-auto max-w-[760px] px-5 py-8 sm:px-8 lg:py-12">
      <div className="mb-10 flex items-center justify-between">
        <BrandMark />
        <span className="font-mono text-micro uppercase tracking-[0.12em] text-ink-3">
          Step {STEPS.indexOf(step) + 1} of {STEPS.length}
        </span>
      </div>

      {step === "upload" ? (
        <>
          <PageHeader
            eyebrow="Optional"
            title={
              <>
                Start with your <em className="text-accent-700">résumé.</em>
              </>
            }
            description="We'll fill in your profile from it: your details, roles, skills and what you're looking for. Company search uses it to find companies hiring people like you, and your outreach emails are written from it. You can skip this and add it later from your profile."
          />
          <ResumeCard onParsed={() => setStep("about")} />
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <Button asChild variant="ghost">
              <Link href={AFTER_AUTH_URL}>Skip for now</Link>
            </Button>
            {profile && (
              <Button variant="primary" onClick={() => setStep("about")}>
                Review my profile <ArrowRight />
              </Button>
            )}
          </div>
        </>
      ) : step === "about" ? (
        <>
          <PageHeader
            eyebrow="Check what we found"
            title={
              <>
                Is this <em className="text-accent-700">you?</em>
              </>
            }
            description="Your outreach emails use your name, headline and pitch, so fix anything we got wrong."
          />
          <GeneralTab title="About you" description={null} onSaved={() => setStep("review")} />
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <Button variant="ghost" onClick={() => setStep("upload")}>
              <ArrowLeft /> Back
            </Button>
            <Button variant="primary" onClick={() => setStep("review")}>
              Next <ArrowRight />
            </Button>
          </div>
        </>
      ) : (
        <>
          <PageHeader
            eyebrow="Check what we found"
            title={
              <>
                Does this look <em className="text-accent-700">like you?</em>
              </>
            }
            description="Fix anything we got wrong. Company search uses this to fill in whatever your search leaves open — what you type always wins."
          />
          <CareerProfileCard title="Your search profile" description={null} onSaved={() => router.push(SEARCH_URL)} />
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <Button variant="ghost" onClick={() => setStep("about")}>
              <ArrowLeft /> Back
            </Button>
            <Button asChild variant="primary">
              <Link href={SEARCH_URL}>
                Looks good, find companies <ArrowRight />
              </Link>
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
