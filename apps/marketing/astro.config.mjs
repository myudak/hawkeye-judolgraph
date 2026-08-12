import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  output: "static",
  integrations: [react()],
  vite: {
    plugins: [tailwindcss()],
  },
  site: process.env.PUBLIC_SITE_URL || "https://hawkeye1.myudak.com",
  build: {
    assets: "assets",
  },
});
