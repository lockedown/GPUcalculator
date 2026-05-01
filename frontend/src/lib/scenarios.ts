"use client";

/**
 * Pinned scenario storage + multi-scenario URL share encoding.
 *
 *   • localStorage: personal pins that persist across browser sessions.
 *   • URL share: /scenarios?compare=<base64-json> for sending a comparison
 *     to a colleague. Pasting the URL imports those scenarios into the
 *     visitor's local pins.
 */

import type { WorkloadInput, ConstraintInput } from "@/types";

const STORAGE_KEY = "gpu-calc-pinned-scenarios";
export const MAX_PINNED = 4;

export interface PinnedScenario {
  id: string;                       // uuid (random)
  name: string;                     // user-editable label
  pinnedAt: string;                 // ISO timestamp
  workload: WorkloadInput;
  constraints: ConstraintInput;
}

function genId(): string {
  // Random 12-char id; fine for in-browser pins (no collision concerns).
  return Math.random().toString(36).slice(2, 14);
}

function safeParse(raw: string | null): PinnedScenario[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed.filter(s => s && s.workload && s.constraints);
  } catch {
    // ignore corrupted JSON
  }
  return [];
}

export function loadPinned(): PinnedScenario[] {
  if (typeof window === "undefined") return [];
  return safeParse(window.localStorage.getItem(STORAGE_KEY));
}

function savePinned(list: PinnedScenario[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

/**
 * Pin the current workload + constraints. Returns the new list, or null if
 * the cap (MAX_PINNED) is already reached.
 */
export function pinScenario(
  workload: WorkloadInput,
  constraints: ConstraintInput,
  name?: string,
): PinnedScenario[] | null {
  const list = loadPinned();
  if (list.length >= MAX_PINNED) return null;
  const pinned: PinnedScenario = {
    id: genId(),
    name: name && name.trim() ? name.trim() : `Scenario ${list.length + 1}`,
    pinnedAt: new Date().toISOString(),
    workload: { ...workload },
    constraints: { ...constraints, metric_weights: { ...constraints.metric_weights } },
  };
  const updated = [...list, pinned];
  savePinned(updated);
  return updated;
}

export function unpinScenario(id: string): PinnedScenario[] {
  const list = loadPinned().filter(s => s.id !== id);
  savePinned(list);
  return list;
}

export function renameScenario(id: string, name: string): PinnedScenario[] {
  const list = loadPinned().map(s => (s.id === id ? { ...s, name } : s));
  savePinned(list);
  return list;
}

export function clearPinned(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}

/**
 * Encode the pinned list into a URL-safe base64 query parameter.
 * Used for /scenarios?compare=...
 */
export function encodePinnedToUrl(scenarios: PinnedScenario[]): string {
  if (typeof window === "undefined") return "";
  // Strip pinnedAt timestamps (re-stamped on import) to keep URLs short.
  const slim = scenarios.map(({ id, name, workload, constraints }) => ({
    id, name, workload, constraints,
  }));
  const json = JSON.stringify(slim);
  // btoa with UTF-8 safety: encodeURIComponent → escape to bytes → btoa
  const b64 = btoa(unescape(encodeURIComponent(json)));
  // Make URL-safe (avoid + / =)
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * Decode the ?compare= param into a list of scenarios. Returns [] on any
 * decoding error (invalid base64, malformed JSON, missing fields).
 */
export function decodeUrlToPinned(b64Url: string): PinnedScenario[] {
  if (typeof window === "undefined" || !b64Url) return [];
  try {
    // Restore base64 alphabet + padding
    const padded = b64Url.replace(/-/g, "+").replace(/_/g, "/");
    const padLen = (4 - (padded.length % 4)) % 4;
    const json = decodeURIComponent(escape(atob(padded + "=".repeat(padLen))));
    const parsed = JSON.parse(json);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(s => s && s.workload && s.constraints)
      .map(s => ({
        id: s.id || genId(),
        name: s.name || "Imported scenario",
        pinnedAt: new Date().toISOString(),
        workload: s.workload,
        constraints: s.constraints,
      }));
  } catch {
    return [];
  }
}

/**
 * Import scenarios from a URL-shared list, merging with existing pins.
 * Caps at MAX_PINNED total.
 */
export function importPinned(scenarios: PinnedScenario[]): PinnedScenario[] {
  const existing = loadPinned();
  const merged = [...existing, ...scenarios].slice(0, MAX_PINNED);
  savePinned(merged);
  return merged;
}
