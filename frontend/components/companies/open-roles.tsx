"use client";

import { ArrowUpRight, RotateCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api/client";
import { useJobPostings } from "@/lib/queries/companies";
import type { JobPosting } from "@/lib/types";

function postedOn(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: sameYear ? undefined : "numeric" });
}

function PostingRow({ posting }: { posting: JobPosting }) {
  const posted = posting.posted_at && postedOn(posting.posted_at);
  const meta = [posting.location, posted && `Posted ${posted}`].filter(Boolean).join(" · ");

  return (
    <li className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 py-2">
      {posting.url ? (
        <a
          href={posting.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-ui font-medium text-ink hover:text-accent-700"
        >
          {posting.title}
          <ArrowUpRight className="size-3 text-ink-3" />
        </a>
      ) : (
        <span className="text-ui font-medium text-ink">{posting.title}</span>
      )}
      {posting.matches_role && <Badge tone="accent">Matches your search</Badge>}
      {meta && <span className="ml-auto text-micro text-ink-3">{meta}</span>}
    </li>
  );
}

export function OpenRoles({ orgId, roles }: { orgId: string; roles: string[] }) {
  const { data, error, isError, refetch, isFetching } = useJobPostings(orgId, roles);

  if (isError) {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 border-t px-5 py-4 text-ui text-ink-2">
        {errorMessage(error)}
        <Button size="sm" onClick={() => refetch()} disabled={isFetching}>
          <RotateCw /> Try again
        </Button>
      </div>
    );
  }

  if (!data) {
    return (
      <div aria-hidden className="animate-pulse space-y-2.5 border-t px-5 py-4">
        <div className="h-3.5 w-1/2 rounded bg-sunken" />
        <div className="h-3.5 w-2/5 rounded bg-sunken" />
        <div className="h-3.5 w-3/5 rounded bg-sunken" />
      </div>
    );
  }

  if (data.total === 0) {
    return <p className="border-t px-5 py-4 text-ui text-ink-3">Apollo has no open postings listed for this company right now.</p>;
  }

  const hidden = data.total - data.postings.length;
  return (
    <div className="border-t px-5 py-3">
      <p className="text-micro text-ink-3">
        {roles.length > 0
          ? `${data.matched_count} of ${data.total} open roles match your search`
          : `${data.total} open roles`}
      </p>
      <ul className="mt-1 divide-y">
        {data.postings.map((posting, i) => (
          <PostingRow key={`${i}-${posting.title}`} posting={posting} />
        ))}
      </ul>
      {hidden > 0 && <p className="pt-1 text-micro text-ink-3">+{hidden.toLocaleString()} more postings</p>}
    </div>
  );
}
