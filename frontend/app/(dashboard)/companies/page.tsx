import type { Metadata } from "next";
import { CompanySearch } from "@/components/companies/company-search";
import { PageHeader } from "@/components/shell/page-header";

export const metadata: Metadata = { title: "Companies" };

export default function CompaniesPage() {
  return (
    <div className="scrollbar-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-[960px] px-5 py-8 sm:px-8 lg:px-10 lg:py-10">
        <PageHeader
          eyebrow="Companies · Hiring now"
          title={
            <>
              Companies <em className="text-accent-700">hiring for you.</em>
            </>
          }
          description="Describe the companies you want in plain words: the role, location, size, industry or age. Every result has open job postings."
        />

        <CompanySearch />
      </div>
    </div>
  );
}
