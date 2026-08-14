export function bootstrapTheme() {
  try {
    const stored = localStorage.getItem("hawkeye-theme")
    const preference = ["dark", "light", "system"].includes(stored ?? "")
      ? stored!
      : "system"
    const resolved =
      preference === "system"
        ? matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light"
        : preference
    const root = document.documentElement
    root.dataset.theme = resolved
    root.dataset.themePreference = preference
    root.className = resolved
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", resolved === "dark" ? "#06111c" : "#f3f6f8")
  } catch {
    // Storage can be unavailable in hardened browser contexts; CSS defaults remain valid.
  }
}

bootstrapTheme()
