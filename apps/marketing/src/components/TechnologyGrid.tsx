import { Badge, Card } from "@hawkeye/ui";

type Technology = {
  image: string;
  name: string;
  id: string;
  en: string;
  optional?: boolean;
};

const technologies: Technology[] = [
  {
    image: "/icon_fastAPI.png",
    name: "Python · FastAPI",
    id: "Menjalankan collector, API lokal, kebijakan, dan ekspor kasus.",
    en: "Runs the collector, local API, policy checks, and case exports.",
  },
  {
    image: "/icon_playwright.png",
    name: "Playwright · Chromium",
    id: "Merender halaman dan menjalankan navigasi publik yang dibatasi.",
    en: "Renders pages and performs bounded public navigation.",
  },
  {
    image: "/icon_sqllite.jpg",
    name: "SQLite · filesystem",
    id: "Menyimpan event append-only, keputusan review, HTML, screenshot, dan hash.",
    en: "Stores append-only events, review decisions, HTML, screenshots, and hashes.",
  },
  {
    image: "/icon_react.png",
    name: "React · Vite",
    id: "Menampilkan graph kasus, inspector bukti, replay, dan timeline.",
    en: "Renders the case graph, evidence inspector, replay, and timeline.",
  },
  {
    image: "/icon_astro.jpg",
    name: "Astro · Tailwind · shadcn",
    id: "Membangun situs produk ini sebagai keluaran statis.",
    en: "Builds this product site as a static output.",
  },
  {
    image: "/icon_openrouter.png",
    name: "OpenAI-compatible LLM",
    id: "Opsional untuk memilih aksi aman. OpenRouter dapat dipakai sebagai provider.",
    en: "Optional for safe action selection. OpenRouter can be used as a provider.",
    optional: true,
  },
  {
    image: "/icon_docker.png",
    name: "Docker",
    id: "Menyediakan runtime lokal yang dapat direproduksi dengan data persisten.",
    en: "Provides a reproducible local runtime with persistent data.",
  },
  {
    image: "/icon_inno.png",
    name: "Inno Setup · Windows",
    id: "Mengemas backend, UI, Chromium, dan OCR sebagai aplikasi Windows.",
    en: "Packages the backend, UI, Chromium, and OCR as a Windows app.",
  },
];

export function TechnologyGrid() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {technologies.map(({ image, name, id, en, optional }) => (
        <Card key={name} className="bg-card/70 p-5">
          <div className="mb-5 flex items-start justify-between gap-3">
            <span className="flex size-12 items-center justify-center overflow-hidden rounded-xl border border-border bg-white p-1.5">
              <img
                className="size-full object-contain"
                src={image}
                alt={`Logo ${name}`}
                loading="lazy"
              />
            </span>
            {optional && (
              <Badge variant="outline">
                <span className="lang-id">Opsional</span>
                <span className="lang-en">Optional</span>
              </Badge>
            )}
          </div>
          <h3 className="text-base font-semibold text-foreground">{name}</h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            <span className="lang-id">{id}</span>
            <span className="lang-en">{en}</span>
          </p>
        </Card>
      ))}
    </div>
  );
}
