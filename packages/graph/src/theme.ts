export type GraphTheme = "dark" | "light";

export interface GraphPalette {
  background: string;
  panel: string;
  seed: string;
  page: string;
  contact: string;
  candidate: string;
  rejected: string;
  offer: string;
  payment: string;
  muted: string;
  grid: string;
  nodeCore: string;
  label: string;
  labelMuted: string;
  labelPlate: string;
  minimap: string;
  minimapLine: string;
  minimapViewport: string;
  tooltip: string;
  cursor: string;
}

export const graphPalettes: Record<GraphTheme, GraphPalette> = {
  dark: {
    background: "#07131f",
    panel: "rgba(4, 14, 23, 0.86)",
    seed: "#ef467f",
    page: "#5b91ef",
    contact: "#27c5ba",
    candidate: "#9b7dde",
    rejected: "#9b687c",
    offer: "#f58a34",
    payment: "#f2c94c",
    muted: "#89a0b0",
    grid: "rgba(143, 163, 181, 0.13)",
    nodeCore: "#0b1824",
    label: "#f5f7fa",
    labelMuted: "#8fa3b5",
    labelPlate: "rgba(5, 15, 24, 0.88)",
    minimap: "rgba(4, 13, 23, 0.94)",
    minimapLine: "rgba(122, 145, 162, 0.24)",
    minimapViewport: "rgba(237, 70, 127, 0.76)",
    tooltip: "rgba(4, 14, 23, 0.94)",
    cursor: "#f5f7fa",
  },
  light: {
    background: "#f5f8fa",
    panel: "rgba(255, 255, 255, 0.9)",
    seed: "#d5165b",
    page: "#276ac3",
    contact: "#087f78",
    candidate: "#7150b5",
    rejected: "#8a6272",
    offer: "#bd5d13",
    payment: "#9a6d00",
    muted: "#5e7382",
    grid: "rgba(56, 88, 110, 0.14)",
    nodeCore: "#ffffff",
    label: "#182733",
    labelMuted: "#5e7382",
    labelPlate: "rgba(255, 255, 255, 0.92)",
    minimap: "rgba(255, 255, 255, 0.94)",
    minimapLine: "rgba(69, 96, 115, 0.28)",
    minimapViewport: "rgba(213, 22, 91, 0.78)",
    tooltip: "rgba(255, 255, 255, 0.96)",
    cursor: "#182733",
  },
};

// Backward-compatible semantic palette. Canvas surfaces should resolve a themed palette.
export const graphPalette = graphPalettes.dark;

export function readGraphTheme(): GraphTheme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export function subscribeGraphTheme(onChange: () => void) {
  if (typeof document === "undefined") return () => undefined;
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme", "class"],
  });
  return () => observer.disconnect();
}

export const graphMotion = {
  cameraEase: 0.12,
  magneticPull: 0.024,
  dragDamping: 0.86,
  releaseDamping: 0.92,
} as const;
