"use client";

import { useEffect, useRef } from "react";
import { useStore } from "./store";
import { encodeStateToParams, decodeParamsToState } from "./url-state";

/**
 * Two-way sync between the Zustand store and the URL query string.
 *
 *   • On mount: parse the current URL and patch workload + constraints into
 *     the store *before* the dashboard fires its initial runComparison.
 *   • On every workload / constraint change: serialise back to the URL via
 *     history.replaceState (no extra browser-history entries while users
 *     drag sliders).
 *
 * Intended to be called once near the top of the dashboard page component.
 */
export function useUrlSync() {
  const setWorkload = useStore((s) => s.setWorkload);
  const setConstraints = useStore((s) => s.setConstraints);
  const workload = useStore((s) => s.workload);
  const constraints = useStore((s) => s.constraints);

  const hydrated = useRef(false);

  // Hydrate from URL on first render (client-side only).
  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    if (typeof window === "undefined") return;

    const search = window.location.search;
    if (!search) return;

    const { workload: w, constraints: c } = decodeParamsToState(search);
    if (Object.keys(w).length > 0) setWorkload(w);
    if (Object.keys(c).length > 0) setConstraints(c);
  }, [setWorkload, setConstraints]);

  // Reflect store state back to URL on every change.
  useEffect(() => {
    if (!hydrated.current) return;
    if (typeof window === "undefined") return;

    const qs = encodeStateToParams(workload, constraints);
    const newUrl = qs
      ? `${window.location.pathname}?${qs}`
      : window.location.pathname;

    // Only update when something actually changed to avoid noisy history calls.
    if (window.location.pathname + window.location.search !== newUrl) {
      window.history.replaceState(null, "", newUrl);
    }
  }, [workload, constraints]);
}
