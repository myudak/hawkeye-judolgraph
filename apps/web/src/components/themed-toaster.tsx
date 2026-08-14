import { Toaster } from "sonner"

import { useTheme } from "@/components/theme-provider"

export function ThemedToaster() {
  const { resolvedTheme } = useTheme()
  return (
    <Toaster
      theme={resolvedTheme}
      richColors
      closeButton
      expand
      visibleToasts={4}
      position="bottom-right"
    />
  )
}
