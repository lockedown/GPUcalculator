import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(n: number | null | undefined, decimals = 0): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toFixed(decimals);
}

export function formatCurrency(n: number | null | undefined): string {
  if (n == null) return "—";
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function ratingColor(rating: string | null): string {
  if (!rating) return "bg-gray-100 text-gray-500";
  const r = rating.toLowerCase();
  if (r.includes("best")) return "bg-blue-50 text-blue-700 border-blue-200";
  if (r.includes("strong")) return "bg-violet-50 text-violet-700 border-violet-200";
  if (r.includes("capable")) return "bg-green-50 text-green-700 border-green-200";
  if (r.includes("baseline")) return "bg-sky-50 text-sky-700 border-sky-200";
  if (r.includes("limited") || r.includes("n/a")) return "bg-orange-50 text-orange-700 border-orange-200";
  return "bg-gray-50 text-gray-600 border-gray-200";
}
