export const demoScenarios = [
  {
    id: "demo-contact",
    seedUrl: "https://harbor.demo.invalid/",
    title: { en: "Public contact trail", id: "Jejak kontak publik" },
    description: {
      en: "Follow two sample pages, inspect a contact and its source screenshot, then export the summary.",
      id: "Telusuri dua halaman contoh, periksa kontak dan screenshot sumbernya, lalu ekspor ringkasan.",
    },
  },
  {
    id: "demo-related",
    seedUrl: "https://tide.demo.invalid/",
    title: { en: "Related-site review", id: "Tinjau situs terkait" },
    description: {
      en: "Reveal a linked sample page after approval and review a public-link assertion. A link does not establish ownership.",
      id: "Buka halaman contoh setelah persetujuan, lalu tinjau klaim tautan publik. Tautan tidak membuktikan kepemilikan.",
    },
  },
  {
    id: "demo-restricted",
    seedUrl: "https://restricted.demo.invalid/",
    title: { en: "Limited capture", id: "Tangkapan terbatas" },
    description: {
      en: "See how a restricted page is preserved without inventing contacts or relationships.",
      id: "Lihat penyimpanan halaman terbatas tanpa menyimpulkan kontak atau relasi yang tidak terlihat.",
    },
  },
] as const
