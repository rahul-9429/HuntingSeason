import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";
import type { Hue } from "@/lib/types";

const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: ["micro", "ui"],
      shadow: ["soft", "raised", "pop"],
      animate: ["enter", "sheet", "overlay", "pop"],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");
}

export function firstName(name: string) {
  return name.split(" ")[0] ?? name;
}

export function timeAgo(iso: string) {
  const minutes = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000);
  if (Number.isNaN(minutes)) return "";
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (minutes < 24 * 60) return `${Math.floor(minutes / 60)}h ago`;
  return `${Math.floor(minutes / (24 * 60))}d ago`;
}

export function formatLakh(value: number) {
  return `₹${value}L`;
}

const HUES: Hue[] = ["slate", "blue", "indigo", "teal", "gray", "sky"];

export function hueFor(seed: string): Hue {
  let hash = 0;
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return HUES[hash % HUES.length]!;
}
