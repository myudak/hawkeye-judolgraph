import { cn } from "@/lib/utils"

const hawkeyeAvatar = "/assets/hawkeye-avatar.png"

export function HawkMark({ className }: { className?: string }) {
  return (
    <span className={cn("hawk-mark", className)} aria-hidden="true">
      <img src={hawkeyeAvatar} alt="" />
    </span>
  )
}

export function BrandLockup({ compact = false }: { compact?: boolean }) {
  return (
    <span className="brand-lockup">
      <HawkMark />
      <span className="min-w-0">
        <strong>HAWK-EYE</strong>
        {compact ? null : <small>ALAT INVESTIGASI EKOSISTEM JUDI ONLINE</small>}
      </span>
    </span>
  )
}
