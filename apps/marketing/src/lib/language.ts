import { useSyncExternalStore } from "react";

export type MarketingLanguage = "id" | "en";

function getLanguage(): MarketingLanguage {
  if (typeof document === "undefined") return "id";
  return document.documentElement.dataset.language === "en" ? "en" : "id";
}

function subscribeLanguage(onChange: () => void) {
  if (typeof document === "undefined") return () => undefined;
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-language"],
  });
  return () => observer.disconnect();
}

export function useMarketingLanguage(): MarketingLanguage {
  return useSyncExternalStore(subscribeLanguage, getLanguage, () => "id");
}

export function localize(
  language: MarketingLanguage,
  copy: { id: string; en: string },
) {
  return copy[language];
}
