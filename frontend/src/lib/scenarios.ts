"use client";

/**
 * Pinned scenario storage + multi-scenario URL share encoding.
 *
 *   • localStorage: personal pins that persist across browser sessions.
 *   • URL share: /scenarios?compare=<base64-json> for sending a comparison
 *     to a colleague. Pasting the URL imports those scenarios into the
 *     visitor's local pins.
 */

import { useEffect, useState } from "react";
import type { WorkloadInput, ConstraintInput } from "@/types";

const STORAGE_KEY = "gpu-calc-pinned-scenarios";
export const MAX_PINNED = 6;

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

// ---------------------------------------------------------------------------
// In-memory subscribers — let any component (dashboard count badge,
// scenarios page) react to add / remove / clear without each one having to
// poll localStorage. The native `storage` event only fires across tabs, not
// within the same tab, so we publish manually after every save.
// ---------------------------------------------------------------------------
type Listener = () => void;
const listeners = new Set<Listener>();

function notify() {
  listeners.forEach(l => l());
}

function savePinned(list: PinnedScenario[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  notify();
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
  notify();
}

/**
 * Clear all pins but return a snapshot first, so the caller can offer Undo.
 * Pair with ``restorePinned`` if the user clicks Undo within the toast window.
 */
export function clearPinnedWithSnapshot(): PinnedScenario[] {
  const snapshot = loadPinned();
  clearPinned();
  return snapshot;
}

/**
 * Restore a previously cleared snapshot. Used by the toast Undo action.
 * If the user pinned new scenarios in the brief Undo window, the snapshot
 * overwrites them — that's the same behaviour as any toast-undo flow and
 * keeps the API simple.
 */
export function restorePinned(snapshot: PinnedScenario[]): void {
  savePinned(snapshot);
}

/**
 * React hook returning the current pinned-scenario count, kept live across
 * pin / unpin / clear within the same tab. Returns 0 during SSR (the count
 * stays accurate after first-mount hydration).
 */
export function usePinnedCount(): number {
  const [count, setCount] = useState<number>(0);
  useEffect(() => {
    const update = () => setCount(loadPinned().length);
    update();
    listeners.add(update);
    // Cross-tab sync — fires only when *another* tab writes.
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) update();
    };
    window.addEventListener("storage", onStorage);
    return () => {
      listeners.delete(update);
      window.removeEventListener("storage", onStorage);
    };
  }, []);
  return count;
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
