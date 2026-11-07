import type { CareerProfile, CompanySize, JobFunction } from "@/lib/types";

export const DEFAULT_SEARCH_EXAMPLES = [
  "SaaS startups in the UAE founded from 2020, 10–200 employees, hiring for sales roles",
  "Fintech companies in Bengaluru hiring backend engineers",
  "Logistics companies in Dubai under 200 employees hiring operations managers",
];

const FUNCTION_TERMS: Record<JobFunction, string> = {
  engineering: "engineering",
  product: "product",
  design: "design",
  data: "data",
  sales: "sales",
  marketing: "marketing",
  customer_success: "customer success",
  finance: "finance",
  operations: "operations",
  hr: "people and HR",
  legal: "legal",
  other: "",
};

function sizeLabel(size: CompanySize): string {
  const [min, max] = size.split(",");
  return `${min}–${max} employees`;
}

function clean(values: (string | null | undefined | false)[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    const trimmed = value ? value.trim() : "";
    if (!trimmed || seen.has(trimmed.toLowerCase())) continue;
    seen.add(trimmed.toLowerCase());
    out.push(trimmed);
  }
  return out;
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function isRemote(place: string): boolean {
  return /^(remote|anywhere|worldwide)$/i.test(place.trim());
}

export function searchSuggestions(profile: CareerProfile | null | undefined): string[] {
  if (!profile) return DEFAULT_SEARCH_EXAMPLES;

  const title = profile.current_title?.trim();
  const functionTerm = profile.function ? FUNCTION_TERMS[profile.function] : "";
  const roleTerm = title ? `${title} roles` : functionTerm ? `${functionTerm} roles` : "";
  const named = clean([...profile.open_to_locations, profile.location]);
  const places = named.filter((place) => !isRemote(place));
  const remote = named.some(isRemote);
  const industries = clean(profile.industries);
  const size = profile.company_size_history[0];

  if (!roleTerm && industries.length === 0 && places.length === 0 && !remote) {
    return DEFAULT_SEARCH_EXAMPLES;
  }

  const hiring = roleTerm ? ` hiring for ${roleTerm}` : " that are hiring";
  const here = places[0] ? ` in ${places[0]}` : "";

  return clean([
    industries[0] && `${capitalize(industries[0])} companies${here}${hiring}`,
    size && `Companies${here}${hiring}, ${sizeLabel(size)}`,
    remote && `Remote-friendly companies${hiring}`,
    places[1] && `Companies in ${places[1]}${hiring}`,
    industries[1] && `${capitalize(industries[1])} companies${hiring}`,
    `Companies${here}${hiring}, with jobs posted in the last 30 days`,
    `Startups${here}${hiring}, founded from 2020`,
    `Companies${here}${hiring}, 11–200 employees`,
    here && `Companies${here}${hiring}`,
  ]).slice(0, 3);
}
