import { cn } from "@/lib/utils"
import { useTheme } from "@/components/theme-provider"

const hawkeyeAvatar = "/assets/hawkeye-avatar.png"
const hawkeyeAvatarLight = "/assets/hawkeye-avatar-light.jpg"
const hawkeyeRadarLight = "/assets/hawkeye-radar-light.jpg"

export function HawkMark({
  className,
  variant = "brand",
}: {
  className?: string
  variant?: "brand" | "radar"
}) {
  const { resolvedTheme } = useTheme()
  const imageSource =
    resolvedTheme === "light"
      ? variant === "radar"
        ? hawkeyeRadarLight
        : hawkeyeAvatarLight
      : hawkeyeAvatar

  return (
    <span className={cn("hawk-mark", className)} aria-hidden="true">
      <img src={imageSource} alt="" />
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
