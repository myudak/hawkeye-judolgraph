import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  output: "static",
  integrations: [react()],
  vite: {
    plugins: [tailwindcss()],
    optimizeDeps: {
      include: ["react", "react/jsx-runtime", "react-dom", "react-dom/client"],
    },
  },
  site: process.env.PUBLIC_SITE_URL || "https://hawkeye.myudak.com",
  build: {
    assets: "assets",
  },
});
