export type ThemePreference = "dark" | "light" | "system";
export type ResolvedTheme = "dark" | "light";

export const THEME_STORAGE_KEY = "hawkeye-theme";
export const THEME_QUERY = "(prefers-color-scheme: dark)";

export function isThemePreference(
  value: string | null,
): value is ThemePreference {
  return value === "dark" || value === "light" || value === "system";
}

export function systemTheme(): ResolvedTheme {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia(THEME_QUERY).matches ? "dark" : "light";
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  return preference === "system" ? systemTheme() : preference;
}

export function storedTheme(
  fallback: ThemePreference = "dark",
): ThemePreference {
  if (typeof localStorage === "undefined") return fallback;
  const value = localStorage.getItem(THEME_STORAGE_KEY);
  return isThemePreference(value) ? value : fallback;
}

export function applyTheme(
  preference: ThemePreference,
  persist = false,
): ResolvedTheme {
  const resolved = resolveTheme(preference);
  if (typeof document !== "undefined") {
    const root = document.documentElement;
    root.dataset.theme = resolved;
    root.dataset.themePreference = preference;
    root.classList.remove("light", "dark");
    root.classList.add(resolved);
    document
      .querySelector<HTMLMetaElement>('meta[name="theme-color"]')
      ?.setAttribute("content", resolved === "dark" ? "#06111c" : "#f3f6f8");
  }
  if (persist && typeof localStorage !== "undefined") {
    localStorage.setItem(THEME_STORAGE_KEY, preference);
  }
  return resolved;
}

export function nextTheme(preference: ThemePreference): ThemePreference {
  if (preference === "dark") return "light";
  if (preference === "light") return "system";
  return "dark";
}
