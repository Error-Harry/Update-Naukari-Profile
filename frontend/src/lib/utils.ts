import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return value;
  }
}

export function timeToString(value: string | null | undefined): string {
  if (!value) return "";
  // Accept "HH:MM" or "HH:MM:SS" -> "HH:MM"
  return value.slice(0, 5);
}
