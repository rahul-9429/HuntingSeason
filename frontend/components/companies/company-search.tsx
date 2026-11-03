"use client";

import { FileText, LoaderCircle, Search, SearchX } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { CompanyCard } from "@/components/companies/company-card";
import { LoadError } from "@/components/shared/load-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";
import { errorMessage } from "@/lib/api/client";
import { type CompanySearchInput, useApolloCreditsLeft, useCompanySearch } from "@/lib/queries/companies";
import { useOutreachCompanies } from "@/lib/queries/outreach";
import { useCareerProfile } from "@/lib/queries/profile";
import { searchSuggestions } from "@/lib/search-suggestions";
import type { CompanyFilters, CompanyRow } from "@/lib/types";

const MAX_ROWS = 1000;

function foundedLabel(from: number | null, to: number | null) {
  if (from && to) return from === to ? `Founded ${from}` : `Founded ${from}–${to}`;
  if (from) return `Founded ${from} or later`;
  if (to) return `Founded ${to} or earlier`;
  return null;
}

function filterLabels(filters: CompanyFilters): string[] {
  return [
    ...filters.hiring_locations.map((location) => `Hiring in ${location}`),
    ...filters.company_locations.map((location) => `HQ in ${location}`),
    ...filters.employee_ranges.map((range) => `${range.replace(",", "–")} employees`),
    ...filters.market_segments,
    ...filters.keyword_tags,
    filters.min_active_job_postings ? `${filters.min_active_job_postings}+ open jobs` : null,
    filters.job_posted_within_days ? `Jobs posted in the last ${filters.job_posted_within_days} days` : null,
    foundedLabel(filters.founded_year_min, filters.founded_year_max),
  ].filter((label): label is string => Boolean(label));
}

function ResultsSkeleton() {
  return (
    <div aria-hidden className="mt-6 space-y-3">
      {Array.from({ length: 3 }, (_, i) => (
        <div key={i} className="flex animate-pulse gap-4 rounded-xl border-2 border-line-strong bg-surface p-5">
          <div className="size-9 rounded-lg bg-sunken" />
          <div className="flex-1 space-y-2.5">
            <div className="h-4 w-1/3 rounded bg-sunken" />
            <div className="h-3 w-1/2 rounded bg-sunken" />
            <div className="h-3 w-2/3 rounded bg-sunken" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function CompanySearch() {
  const [draft, setDraft] = useState("");
  const [submitted, setSubmitted] = useState<CompanySearchInput | null>(null);
  const [profileOn, setProfileOn] = useState(true);
  const search = useCompanySearch(submitted);
  const { data: profile } = useCareerProfile();
  const examples = searchSuggestions(profile);
  const useProfile = Boolean(profile) && profileOn;

  const pages = search.data?.pages ?? [];
  const first = pages[0];
  const seen = new Set<string>();
  const rows: CompanyRow[] = [];
  for (const row of pages.flatMap((page) => page.rows)) {
    if (seen.has(row.apollo_org_id)) continue;
    seen.add(row.apollo_org_id);
    rows.push(row);
  }

  const searching = search.isFetching && !search.isFetchingNextPage;
  const creditsLeft = useApolloCreditsLeft();
  const { data: outreach } = useOutreachCompanies();
  const outreachByOrg = new Map(outreach?.map((c) => [c.apollo_org_id, c]));

  function submit(text: string) {
    const trimmed = text.trim();
    if ((!trimmed && !useProfile) || searching) return;
    const same = submitted?.query === trimmed && submitted.useProfile === useProfile;
    if (same && search.isError && !search.data) void search.refetch();
    else setSubmitted({ query: trimmed, useProfile });
  }

  return (
    <section aria-label="Company search" className="min-w-0">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit(draft);
        }}
        className="rounded-xl border-2 border-line-strong bg-surface p-4"
      >
        <label htmlFor="company-query" className="sr-only">
          Describe the companies you want
        </label>
        <Textarea
          id="company-query"
          rows={2}
          maxLength={1000}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              submit(draft);
            }
          }}
          placeholder={
            useProfile
              ? "Describe the companies you want, or leave empty to search from your résumé"
              : `e.g. ${examples[0]}`
          }
          className="border-0 px-0 shadow-none hover:border-0 focus:ring-0"
        />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {examples.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => {
                setDraft(example);
                submit(example);
              }}
              className="cursor-pointer rounded-full border px-2.5 py-1 text-left text-micro text-ink-2 transition hover:border-line-strong hover:text-ink"
            >
              {example}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-3">
            {profile ? (
              <label className="flex cursor-pointer items-center gap-2 text-micro text-ink-2">
                <Switch checked={profileOn} onCheckedChange={setProfileOn} />
                Use my résumé
              </label>
            ) : (
              profile === null && (
                <Link
                  href="/profile?tab=resume"
                  className="flex items-center gap-1 text-micro text-ink-3 underline-offset-2 hover:text-ink hover:underline"
                >
                  <FileText className="size-3.5" /> Add your résumé to personalize
                </Link>
              )
            )}
            <Button type="submit" variant="primary" disabled={(!draft.trim() && !useProfile) || searching}>
              {searching ? <LoaderCircle className="animate-spin" /> : <Search />}
              {draft.trim() || !useProfile ? "Search" : "Search from my résumé"}
            </Button>
          </div>
        </div>
      </form>

      {!submitted ? null : search.isError && !search.data ? (
        <LoadError
          what="companies"
          detail={errorMessage(search.error)}
          onRetry={() => search.refetch()}
          className="mt-6"
        />
      ) : !first ? (
        <ResultsSkeleton />
      ) : (
        <div className="mt-6">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-micro text-ink-3">Searched for</span>
            {first.used_profile && (
              <Badge tone="accent">
                <FileText /> Personalized from résumé
              </Badge>
            )}
            {filterLabels(first.filters).map((label, i) => (
              <Badge key={i}>{label}</Badge>
            ))}
            {first.filters.job_title_signals.map((role, i) => (
              <Badge key={`role-${i}`} tone="accent">
                Hiring: {role}
              </Badge>
            ))}
          </div>

          <div className="mt-5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 className="text-[15px] font-semibold tracking-tight text-ink">
              {first.total_entries != null
                ? `${first.total_entries.toLocaleString()} companies hiring`
                : `${rows.length} companies hiring`}
              {first.total_entries != null && first.total_entries > rows.length && (
                <span className="ml-2 text-ui font-normal text-ink-3">showing {rows.length.toLocaleString()}</span>
              )}
            </h2>
            {creditsLeft != null && (
              <p className="text-micro text-ink-3">
                {creditsLeft} search {creditsLeft === 1 ? "credit" : "credits"} left
              </p>
            )}
          </div>

          {rows.length === 0 ? (
            <div className="mt-4 rounded-xl border border-dashed bg-surface/60 px-6 py-14 text-center">
              <SearchX className="mx-auto size-5 text-ink-3" />
              <p className="mt-2 text-ui font-medium text-ink">No hiring companies matched</p>
              <p className="mt-1 text-micro text-ink-3">Try a wider location, a broader role or fewer filters.</p>
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {rows.map((company) => (
                <CompanyCard
                  key={company.apollo_org_id}
                  company={company}
                  roles={first.filters.job_title_signals}
                  locations={
                    first.filters.hiring_locations.length > 0
                      ? first.filters.hiring_locations
                      : first.filters.company_locations
                  }
                  outreach={outreachByOrg.get(company.apollo_org_id)}
                />
              ))}
            </div>
          )}

          <div className="mt-6 flex flex-col items-center gap-2 text-center">
            {search.isFetchNextPageError && (
              <p role="alert" className="text-ui text-ink-2">
                {errorMessage(search.error)}
              </p>
            )}
            {search.hasNextPage ? (
              <Button onClick={() => search.fetchNextPage()} disabled={search.isFetchingNextPage}>
                {search.isFetchingNextPage && <LoaderCircle className="animate-spin" />}
                {search.isFetchNextPageError ? "Try again" : "Load more"}
              </Button>
            ) : (
              rows.length >= MAX_ROWS && (
                <p className="text-micro text-ink-3">
                  Showing the first {MAX_ROWS.toLocaleString()}. Narrow your search to see others.
                </p>
              )
            )}
          </div>
        </div>
      )}
    </section>
  );
}
