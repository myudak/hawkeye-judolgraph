(() => {
  try {
    const saved = localStorage.getItem("hawkeye-theme");
    const preference = ["dark", "light", "system"].includes(saved)
      ? saved
      : "system";
    const theme =
      preference === "system"
        ? matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light"
        : preference;
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.dataset.themePreference = preference;
    root.classList.remove("light", "dark");
    root.classList.add(theme);
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "dark" ? "#06111c" : "#f3f6f8");

    const language = localStorage.getItem("hawkeye-language");
    if (language === "id" || language === "en") {
      root.dataset.language = language;
      root.lang = language;
    }
  } catch {}
})();
