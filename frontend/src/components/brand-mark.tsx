import { Eye } from "@phosphor-icons/react"

import { cn } from "@/lib/utils"

export function HawkMark({ className }: { className?: string }) {
  return (
    <span className={cn("hawk-mark", className)} aria-hidden="true">
      <svg viewBox="0 0 72 72" role="presentation">
        <path
          className="hawk-wing"
          d="M8 13c17 1 30 7 41 18l15-4-9 12c4 7 5 15 3 23-9-9-20-14-34-14L13 60l3-18-11-9 15 1C14 27 10 20 8 13Z"
        />
        <path className="hawk-cut" d="m30 28 19 4-12 10-15-6 8-8Z" />
        <circle className="hawk-eye" cx="40" cy="33" r="3" />
      </svg>
    </span>
  )
}

export function BrandLockup({ compact = false }: { compact?: boolean }) {
  return (
    <span className="brand-lockup">
      <HawkMark />
      <span className="min-w-0">
        <strong>HAWK-EYE</strong>
        {compact ? null : (
          <small>
            <Eye weight="fill" /> JUDOLGRAPH · EVIDENCE INSTRUMENT
          </small>
        )}
      </span>
    </span>
  )
}
