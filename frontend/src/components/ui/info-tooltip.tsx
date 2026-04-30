"use client";

import Link from "next/link";
import { Info } from "lucide-react";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";

interface InfoTooltipProps {
  /** Short, scan-friendly explanation. ~1–3 short sentences. */
  children: React.ReactNode;
  /** Optional anchor on /methodology to deep-link to. e.g. "tco" → /methodology#tco */
  learnMore?: string;
  /** Optional class for the icon. */
  iconClassName?: string;
  /** Optional label for screen readers (defaults to "More info"). */
  ariaLabel?: string;
}

/**
 * A compact ⓘ icon next to a label or value. Hovering / focusing it pops a
 * tooltip with a brief explanation and an optional link into the full
 * Methodology page.
 *
 * Usage:
 *   <label>Model Size <InfoTooltip learnMore="inputs">…</InfoTooltip></label>
 */
export function InfoTooltip({
  children,
  learnMore,
  iconClassName = "h-3 w-3",
  ariaLabel = "More info",
}: InfoTooltipProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={ariaLabel}
          className="inline-flex items-center justify-center text-gray-400 hover:text-gray-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded-sm align-middle"
        >
          <Info className={iconClassName} aria-hidden="true" />
        </button>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        align="start"
        className="max-w-xs px-3 py-2 text-[11px] leading-relaxed bg-gray-900 text-white"
      >
        <div className="space-y-1.5">
          <div>{children}</div>
          {learnMore && (
            <Link
              href={`/methodology#${learnMore}`}
              className="inline-flex items-center gap-0.5 text-blue-300 hover:text-blue-200 underline-offset-2 hover:underline"
            >
              Learn more →
            </Link>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
