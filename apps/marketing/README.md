# HAWK-EYE Marketing

Static Astro marketing site for HAWK-EYE. It is intentionally isolated from the React investigation
console in `apps/web` and from the Python/Windows packaging pipeline.

```powershell
pnpm dev:marketing
pnpm build:marketing
```

The development server defaults to `http://localhost:4321`. Copy `.env.example` to `.env` inside
this directory only when deployment-specific public URLs are needed. The Windows CTA falls back to
the GitHub Releases page until `PUBLIC_WINDOWS_DOWNLOAD_URL` points at a published installer.
