"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";

interface NumericInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> {
  value: number | null;
  onChange: (value: number | null) => void;
  min?: number;
  max?: number;
  // Value used to populate the input when the field is cleared and `null`
  // is not allowed (i.e. nullable=false). Defaults to `min` if provided, else 0.
  fallback?: number;
  // If true, allow the user to fully clear the field — onChange is called with null.
  nullable?: boolean;
}

/**
 * Numeric input that lets the user type freely (including transient empty/intermediate
 * states) and only commits a clamped, validated number on blur. Solves the classic
 * "default value snaps back to 1 the moment I hit backspace" bug from the prior
 * `value={x} onChange={(e) => set(+e.target.value || 1)}` pattern.
 *
 * Behaviour on blur:
 *   - empty field + nullable=true  → onChange(null)
 *   - empty field + nullable=false → onChange(fallback ?? min ?? 0)
 *   - non-numeric / NaN            → revert to last committed value
 *   - below min / above max        → clamp to the nearest valid value
 */
export function NumericInput({
  value,
  onChange,
  min,
  max,
  fallback,
  nullable = false,
  onBlur,
  ...rest
}: NumericInputProps) {
  // Local string state lets the user type "" or "1." or "-" etc. transiently
  // without the parent state stamping over it on every keystroke.
  const [draft, setDraft] = React.useState<string>(value === null ? "" : String(value));

  // Re-sync draft when the parent value changes from outside (e.g. reset).
  React.useEffect(() => {
    setDraft(value === null ? "" : String(value));
  }, [value]);

  function commit() {
    if (draft === "") {
      if (nullable) {
        onChange(null);
        return;
      }
      const fb = fallback ?? min ?? 0;
      setDraft(String(fb));
      onChange(fb);
      return;
    }

    const parsed = Number(draft);
    if (!Number.isFinite(parsed)) {
      // Revert to last committed value
      setDraft(value === null ? "" : String(value));
      return;
    }

    let clamped = parsed;
    if (min !== undefined && clamped < min) clamped = min;
    if (max !== undefined && clamped > max) clamped = max;

    setDraft(String(clamped));
    onChange(clamped);
  }

  return (
    <Input
      type="text"
      inputMode="decimal"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={(e) => {
        commit();
        onBlur?.(e);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          (e.target as HTMLInputElement).blur();
        }
      }}
      {...rest}
    />
  );
}
