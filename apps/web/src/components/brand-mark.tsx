import { cn } from "@/lib/utils"
import { useTheme } from "@/components/theme-provider"
import { isDemo, publicAssetUrl } from "@/lib/runtime"

const hawkeyeAvatar = publicAssetUrl("hawkeye-avatar.png")
const hawkeyeAvatarLight = publicAssetUrl("hawkeye-avatar-light.jpg")
const hawkeyeRadarLight = publicAssetUrl("hawkeye-radar-light.jpg")

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
        {compact ? null : (
          <small className={isDemo ? "demo-label" : undefined}>
            {isDemo
              ? "Demo · Sample data"
              : "ALAT INVESTIGASI EKOSISTEM JUDI ONLINE"}
          </small>
        )}
      </span>
    </span>
  )
}
