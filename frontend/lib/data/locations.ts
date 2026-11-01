import type { TargetLocation } from "@/lib/types";

export const locationOptions: { country: string; cities: string[] }[] = [
  { country: "India", cities: ["Bengaluru", "Hyderabad", "Pune", "Mumbai", "Delhi NCR", "Chennai"] },
  { country: "Singapore", cities: [] },
  { country: "United Arab Emirates", cities: ["Dubai", "Abu Dhabi"] },
  { country: "United Kingdom", cities: ["London", "Manchester"] },
  { country: "Germany", cities: ["Berlin", "Munich"] },
  { country: "Netherlands", cities: ["Amsterdam"] },
  { country: "Canada", cities: ["Toronto", "Vancouver"] },
  { country: "United States", cities: ["San Francisco Bay Area", "New York", "Seattle"] },
  { country: "Australia", cities: ["Sydney", "Melbourne"] },
];

export function locationLabel(location: TargetLocation) {
  return location.city ? `${location.city}, ${location.country}` : `Anywhere in ${location.country}`;
}

export function sameLocation(a: TargetLocation, b: TargetLocation) {
  return a.country === b.country && (a.city ?? "") === (b.city ?? "");
}
