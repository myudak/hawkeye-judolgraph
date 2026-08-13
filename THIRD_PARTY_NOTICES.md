# Third-Party Notices

This file records the dependency-license audit for the HAWK-EYE 1.0.0
competition snapshot on 2026-08-13. It is informational and does not replace
the license text or notice file distributed by an upstream project. Exact
versions are owned by `uv.lock` and `pnpm-lock.yaml`.

## Python runtime dependencies

| Component | Locked version | SPDX license | Purpose |
|---|---:|---|---|
| beautifulsoup4 | 4.15.0 | MIT | Deterministic HTML parsing |
| FastAPI | 0.141.1 | MIT | Local API and application routes |
| Pillow | 12.3.0 | MIT-CMU | Image inspection, metrics, and crops |
| Playwright | 1.50.0 | Apache-2.0 | Bounded Chromium automation |
| Pydantic | 2.13.4 | MIT | Runtime schema validation |
| tldextract | 5.3.2 | BSD-3-Clause | Domain normalization |
| Uvicorn | 0.52.1 | BSD-3-Clause | Local ASGI server |

## Python development, build, and desktop dependencies

| Component | Locked version | SPDX license | Distribution note |
|---|---:|---|---|
| httpx | 0.28.1 | BSD-3-Clause | Test-only API client |
| mypy | 2.3.0 | MIT | Type checking |
| pytest | 9.1.1 | MIT | Test runner |
| pytest-xdist | 3.8.0 | MIT | Parallel test execution |
| Ruff | 0.16.2 | MIT | Formatting and linting |
| types-beautifulsoup4 | 4.12.0.20250516 | Apache-2.0 | Type stubs |
| PyInstaller | 6.21.0 | GPL-2.0-or-later WITH Bootloader-exception | Windows bundle builder; preserve the upstream exception and notices |
| pystray | 0.19.5 | LGPL-3.0-only | Windows notification-area control; preserve LGPL notices |
| setuptools | 84.0.0 | MIT | Python package build backend |

## JavaScript direct dependencies

The React application and Astro presentation site directly use the following
external packages. Internal `@hawkeye/*` workspace packages are project-authored
and covered by the repository MIT license.

| Component | Locked version | SPDX license |
|---|---:|---|
| @astrojs/react | 4.4.2 | MIT |
| @base-ui/react | 1.7.0 | MIT |
| @fontsource-variable/geist | 5.3.0 | OFL-1.1 |
| @fontsource-variable/newsreader | 5.3.0 | OFL-1.1 |
| @fontsource-variable/public-sans | 5.3.0 | OFL-1.1 |
| @phosphor-icons/react | 2.1.10 | MIT |
| @tailwindcss/vite | 4.3.3 | MIT |
| @tanstack/react-query | 5.101.4 | MIT |
| Astro | 7.2.1 | MIT |
| class-variance-authority | 0.7.1 | Apache-2.0 |
| clsx | 2.1.1 | MIT |
| React | 19.2.8 | MIT |
| React DOM | 19.2.8 | MIT |
| React Router DOM | 7.18.2 | MIT |
| shadcn | 4.16.2 | MIT |
| Sonner | 2.0.8 | MIT |
| tailwind-merge | 3.6.0 | MIT |
| Tailwind CSS | 4.3.3 | MIT |
| tw-animate-css | 1.4.0 | MIT |

Direct JavaScript development tools are MIT unless noted: `@astrojs/check`
0.9.10, `@eslint/js` 10.0.1, `@types/node` 24.13.3, `@types/react`
19.2.18, `@types/react-dom` 19.2.4, `@vitejs/plugin-react` 6.0.5,
`concurrently` 9.2.4, `eslint` 10.8.1, `eslint-plugin-react-hooks` 7.1.1,
`eslint-plugin-react-refresh` 0.5.3, `globals` 17.9.0, `prettier` 3.9.6,
`prettier-plugin-astro` 0.14.1, `prettier-plugin-tailwindcss` 0.8.1,
`typescript-eslint` 8.66.0, `vite` 8.2.1, and `vitest` 4.1.10.
`typescript` 6.0.3 is Apache-2.0.

## Locked production JavaScript graph

`pnpm licenses list --prod --json` produced the following package-name records
on 2026-08-13. Counts are audit records, not a claim that every package is
embedded in every distribution format.

| Declared license | Records |
|---|---:|
| MIT | 430 |
| ISC | 24 |
| BSD-2-Clause | 12 |
| BSD-3-Clause | 8 |
| Apache-2.0 | 8 |
| BlueOak-1.0.0 | 5 |
| OFL-1.1 | 3 |
| MPL-2.0 | 2 |
| Apache-2.0 AND LGPL-3.0-or-later | 1 |
| CC-BY-4.0 | 1 |
| CC0-1.0 | 1 |
| Python-2.0 | 1 |
| 0BSD | 1 |

Notable records include the Fontsource font packages (OFL-1.1),
`@img/sharp-win32-x64` 0.35.3 (Apache-2.0 AND LGPL-3.0-or-later),
`lightningcss` and its Windows binary (MPL-2.0), `caniuse-lite`
(CC-BY-4.0), and `mdn-data` (CC0-1.0). Preserve their upstream notice and
license files whenever the corresponding material is redistributed.

## Bundled or optional runtimes

- Python is distributed under the PSF License Agreement; its own third-party
  notices remain applicable.
- SQLite source is dedicated to the public domain.
- Playwright Chromium is BSD-3-Clause with numerous third-party notices. The
  complete Chromium license and notice set must accompany a redistributed
  browser bundle.
- Optional Tesseract OCR is Apache-2.0 and is not included unless an explicitly
  reviewed build input supplies it.
- Node.js and pnpm are MIT-licensed development/runtime tools. `uv` is dual
  licensed Apache-2.0 OR MIT.
- Inno Setup uses its own permissive license; the installed license text and
  third-party notices must remain with the Windows installer toolchain.

## Redistribution rule

Before packaging a release, regenerate both lockfile audits, copy every
applicable upstream license/notice file into the distribution, retain source or
modification obligations for LGPL/MPL-covered components, and verify the
actual contents of the wheel, portable ZIP, installer, container, and website
separately. A lockfile change invalidates this snapshot until the audit is rerun.
