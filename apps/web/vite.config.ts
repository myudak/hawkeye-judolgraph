import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/assets/" : "/",
  publicDir: path.resolve(import.meta.dirname, "./src/assets"),
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  build: {
    outDir: path.resolve(
      import.meta.dirname,
      "../api/src/hawkeye/review_app/static"
    ),
    emptyOutDir: true,
    sourcemap: false,
    cssCodeSplit: false,
    assetsInlineLimit: 4_096,
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: (assetInfo) =>
          assetInfo.name?.endsWith(".css")
            ? "styles.css"
            : "[name]-[hash][extname]",
      },
    },
  },
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8760",
        changeOrigin: true,
        configure(proxy) {
          proxy.on("proxyReq", (request) => {
            request.setHeader("origin", "http://127.0.0.1:8760")
          })
        },
      },
      "/health": {
        target: "http://127.0.0.1:8760",
        changeOrigin: true,
      },
    },
  },
}))
