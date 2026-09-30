import path from "path"
import fs from "node:fs"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig(({ command, mode }) => ({
  base: mode === "demo" ? "./" : command === "build" ? "/assets/" : "/",
  publicDir: path.resolve(import.meta.dirname, "./src/assets"),
  plugins: [
    react(),
    tailwindcss(),
    ...(mode === "demo"
      ? [
          {
            name: "hawkeye-static-demo",
            transformIndexHtml(html: string) {
              return html
                .replace(
                  /<title>.*?<\/title>/,
                  "<title>HAWK-EYE · Interactive demo</title>"
                )
                .replace(
                  /(<meta\s+(?:name|property)="(?:description|og:description|twitter:description)"\s+content=")[^"]*(")/g,
                  "$1Explore a fictional investigation: capture playback, evidence graph, provenance, and human review. Runs without a backend.$2"
                )
            },
            writeBundle() {
              const file = path.resolve(
                import.meta.dirname,
                "dist-demo/site.webmanifest"
              )
              const manifest = JSON.parse(fs.readFileSync(file, "utf8"))
              fs.writeFileSync(
                file,
                JSON.stringify(
                  {
                    ...manifest,
                    id: "./",
                    start_url: "./",
                    scope: "./",
                    name: "HAWK-EYE demo",
                    short_name: "HAWK-EYE demo",
                  },
                  null,
                  2
                )
              )
            },
          },
        ]
      : []),
  ],
  resolve: {
    alias: {
      "@/api/transport": path.resolve(
        import.meta.dirname,
        mode === "demo" ? "./src/demo/client.ts" : "./src/api/live-client.ts"
      ),
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  build: {
    outDir:
      mode === "demo"
        ? path.resolve(import.meta.dirname, "dist-demo")
        : path.resolve(
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
    proxy:
      mode === "demo"
        ? undefined
        : {
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
