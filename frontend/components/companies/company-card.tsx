"use client";

import {
  ArrowUpRight,
  BriefcaseBusiness,
  CalendarDays,
  Check,
  ChevronDown,
  Globe,
  LoaderCircle,
  UserPlus,
  UserX,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { OpenRoles } from "@/components/companies/open-roles";
import { LinkedInGlyph } from "@/components/shared/brand-icons";
import { CompanyMark } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useApolloCreditsLeft } from "@/lib/queries/companies";
import { useAddToOutreach } from "@/lib/queries/outreach";
import type { CompanyRow, OutreachCompany } from "@/lib/types";
import { cn, hueFor } from "@/lib/utils";

function withScheme(url: string) {
  return /^https?:\/\//i.test(url) ? url : `https://${url}`;
}

function bareDomain(url: string) {
  return url.replace(/^https?:\/\//i, "").replace(/^www\./i, "").replace(/\/.*$/, "");
}

function OutreachButton({
  company,
  roles,
  locations,
  outreach,
}: {
  company: CompanyRow;
  roles: string[];
  locations: string[];
  outreach: OutreachCompany | undefined;
}) {
  const add = useAddToOutreach();

  function addCompany() {
    add.mutate({ apolloOrgId: company.apollo_org_id, roles, locations });
  }

  if (add.isPending || outreach?.status === "searching") {
    return (
      <span role="status" className="ml-auto flex items-center gap-1.5 px-1 text-micro text-ink-3">
        <LoaderCircle className="size-3.5 animate-spin" />
        Finding contacts…
      </span>
    );
  }
  if (outreach?.status === "ready") {
    const found = outreach.contacts_found;
    return (
      <Link href="/contacts" className="group ml-auto flex items-center gap-1.5 px-1 text-micro text-ink-2 hover:text-ink">
        <Check className="size-3.5 text-accent-700" />
        {found} {found === 1 ? "contact" : "contacts"} added
        <span className="font-medium text-accent-700 group-hover:text-accent-800">View</span>
      </Link>
    );
  }
  if (outreach?.status === "no_contacts") {
    return (
      <span className="ml-auto flex items-center gap-1.5 px-1 text-micro text-ink-3">
        <UserX className="size-3.5" />
        No contacts found here
      </span>
    );
  }
  if (outreach?.status === "failed") {
    return (
      <span title={outreach.error ?? undefined} className="ml-auto flex items-center gap-2 px-1 text-micro text-ink-2">
        Couldn’t find contacts
        <button
          type="button"
          onClick={addCompany}
          className="cursor-pointer font-medium text-accent-700 hover:text-accent-800"
        >
          Try again
        </button>
      </span>
    );
  }
  return (
    <Button
      size="sm"
      variant="secondary"
      onClick={addCompany}
      title="Finds up to 2 people here who can get you in, with their full name, LinkedIn and verified email. About 1 credit per person, free if someone found them before."
      className="ml-auto"
    >
      <UserPlus className="text-accent-700" />
      Add to contacts
    </Button>
  );
}

interface CompanyCardProps {
  company: CompanyRow;
  roles: string[];
  locations: string[];
  outreach: OutreachCompany | undefined;
}

export function CompanyCard({ company, roles, locations, outreach }: CompanyCardProps) {
  const [showRoles, setShowRoles] = useState(false);
  const noCreditsLeft = useApolloCreditsLeft() === 0;

  return (
    <article className="rounded-xl border-2 border-line-strong bg-surface transition-colors hover:border-line-strong">
      <div className="flex gap-4 p-5">
        <CompanyMark name={company.company_name} hue={hueFor(company.company_name)} size="lg" />

        <div className="min-w-0 flex-1">
          <h3 className="text-[15px] font-semibold tracking-tight text-ink">{company.company_name}</h3>

          <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-micro text-ink-2">
            {company.domain && (
              <a
                href={withScheme(company.domain)}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 hover:text-ink"
              >
                <Globe className="size-3.5 text-ink-3" />
                {bareDomain(company.domain)}
              </a>
            )}
            {company.linkedin_url && (
              <a
                href={withScheme(company.linkedin_url)}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 hover:text-ink"
              >
                <LinkedInGlyph />
                LinkedIn
              </a>
            )}
            {company.founded_year && (
              <span className="flex items-center gap-1.5">
                <CalendarDays className="size-3.5 text-ink-3" />
                Founded {company.founded_year}
              </span>
            )}
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-ui text-ink-2">
            <BriefcaseBusiness className="size-3.5 shrink-0 text-accent-700" />
            {roles.length > 0 ? (
              <>
                Hiring for one of
                {roles.map((role, i) => (
                  <Badge key={i} tone="accent">
                    {role}
                  </Badge>
                ))}
              </>
            ) : (
              "Actively hiring"
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t px-5 py-2">
        {company.linkedin_jobs_url && (
          <Button asChild size="sm" variant="secondary">
            <a href={company.linkedin_jobs_url} target="_blank" rel="noreferrer">
              <LinkedInGlyph />
              Jobs on LinkedIn
              <ArrowUpRight className="text-ink-3" />
            </a>
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          aria-expanded={showRoles}
          disabled={!showRoles && noCreditsLeft}
          onClick={() => setShowRoles((open) => !open)}
          title={noCreditsLeft ? "No search credits left" : "Lists this company’s postings here"}
        >
          <ChevronDown className={cn("transition-transform", showRoles && "rotate-180")} />
          {showRoles ? "Hide postings" : "Fetch postings here"}
          {!showRoles && <span className="font-normal text-ink-3">· 1 credit</span>}
        </Button>
        <OutreachButton company={company} roles={roles} locations={locations} outreach={outreach} />
      </div>

      {showRoles && <OpenRoles orgId={company.apollo_org_id} roles={roles} />}
    </article>
  );
}
