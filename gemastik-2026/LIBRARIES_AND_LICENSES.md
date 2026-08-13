# Daftar Komponen/Software Library dan Lisensi

**Produk:** HAWK-EYE — JudolGraph
**Versi audit:** 1.0.0
**Snapshot:** 13 Agustus 2026
**Sumber versi:** `uv.lock` dan `pnpm-lock.yaml`

Dokumen ini mencatat komponen langsung yang digunakan aplikasi, komponen
pengembangan/pemaketan, runtime yang dapat dibundel, serta ringkasan seluruh
graf dependensi produksi JavaScript. Nama lisensi menggunakan pengenal SPDX
berdasarkan metadata paket terkunci dan berkas lisensi upstream.

## A. Komponen buatan proyek

| Komponen | Fungsi | Lisensi |
|---|---|---|
| `apps/api` / `judolgraph-hawkeye` | Kolektor, ekstraksi, agent runtime, penyimpanan event, API lokal, ekspor | MIT |
| `apps/web` | Antarmuka React untuk investigasi, graf, inspector, timeline, dan ringkasan | MIT |
| `apps/marketing` | Situs presentasi Astro | MIT |
| `@hawkeye/brand` | Logo dan aset identitas antarmuka | MIT |
| `@hawkeye/design` | Token dan stylesheet desain | MIT |
| `@hawkeye/graph` | Komponen graf bukti dan simulasi gaya | MIT |
| `@hawkeye/ui` | Komponen antarmuka bersama | MIT |

Lisensi proyek diadopsi melalui `LICENSE` pada akar repositori. Cakupannya
tidak mengubah lisensi komponen pihak ketiga.

## B. Library Python — runtime aplikasi

| Library | Versi terkunci | Fungsi | Lisensi SPDX | Sumber |
|---|---:|---|---|---|
| beautifulsoup4 | 4.15.0 | Parsing HTML deterministik | MIT | pypi.org/project/beautifulsoup4 |
| FastAPI | 0.141.1 | API lokal dan rute aplikasi | MIT | pypi.org/project/fastapi |
| Pillow | 12.3.0 | Inspeksi gambar, metrik, dan crop bukti | MIT-CMU | pypi.org/project/Pillow |
| Playwright | 1.50.0 | Kendali Chromium berbatas | Apache-2.0 | pypi.org/project/playwright |
| Pydantic | 2.13.4 | Validasi skema runtime | MIT | pypi.org/project/pydantic |
| tldextract | 5.3.2 | Normalisasi domain | BSD-3-Clause | pypi.org/project/tldextract |
| Uvicorn | 0.52.1 | Server ASGI pada localhost | BSD-3-Clause | pypi.org/project/uvicorn |

## C. Library Python — pengembangan, build, dan desktop

| Library | Versi terkunci | Fungsi | Lisensi SPDX |
|---|---:|---|---|
| httpx | 0.28.1 | Pengujian API | BSD-3-Clause |
| mypy | 2.3.0 | Pemeriksaan tipe statis | MIT |
| pytest | 9.1.1 | Kerangka pengujian | MIT |
| pytest-xdist | 3.8.0 | Eksekusi test paralel | MIT |
| Ruff | 0.16.2 | Formatter dan linter | MIT |
| types-beautifulsoup4 | 4.12.0.20250516 | Stub tipe | Apache-2.0 |
| setuptools | 84.0.0 | Backend build paket Python | MIT |
| PyInstaller | 6.21.0 | Pembentukan aplikasi Windows | GPL-2.0-or-later WITH Bootloader-exception |
| pystray | 0.19.5 | Kontrol notification area Windows | LGPL-3.0-only |

Pengecualian bootloader PyInstaller memungkinkan pendistribusian aplikasi yang
dibentuk dengannya tanpa menjadikan aplikasi tersebut otomatis berlisensi GPL.
Teks pengecualian dan notice upstream tetap harus dipertahankan. Pystray hanya
masuk varian desktop Windows dan kewajiban LGPL-nya diperiksa saat redistribusi.

## D. Library JavaScript — runtime aplikasi dan situs

| Library | Versi terkunci | Fungsi | Lisensi SPDX |
|---|---:|---|---|
| @astrojs/react | 4.4.2 | Integrasi React pada Astro | MIT |
| @base-ui/react | 1.7.0 | Primitif UI aksesibel | MIT |
| @fontsource-variable/geist | 5.3.0 | Font Geist lokal | OFL-1.1 |
| @fontsource-variable/newsreader | 5.3.0 | Font Newsreader lokal | OFL-1.1 |
| @fontsource-variable/public-sans | 5.3.0 | Font Public Sans lokal | OFL-1.1 |
| @phosphor-icons/react | 2.1.10 | Ikon vektor | MIT |
| @tailwindcss/vite | 4.3.3 | Integrasi Tailwind–Vite | MIT |
| @tanstack/react-query | 5.101.4 | Sinkronisasi data API pada UI | MIT |
| Astro | 7.2.1 | Pembangun situs presentasi | MIT |
| class-variance-authority | 0.7.1 | Variasi kelas komponen | Apache-2.0 |
| clsx | 2.1.1 | Komposisi nama kelas | MIT |
| React | 19.2.8 | Kerangka antarmuka | MIT |
| React DOM | 19.2.8 | Renderer DOM React | MIT |
| React Router DOM | 7.18.2 | Routing sisi klien | MIT |
| shadcn | 4.16.2 | Tooling komponen UI | MIT |
| Sonner | 2.0.8 | Notifikasi toast | MIT |
| tailwind-merge | 3.6.0 | Penggabungan kelas Tailwind | MIT |
| Tailwind CSS | 4.3.3 | Sistem styling | MIT |
| tw-animate-css | 1.4.0 | Utilitas animasi CSS | MIT |

## E. Tool JavaScript — pengembangan dan build

Tool berikut berlisensi MIT pada versi terkunci: `@astrojs/check` 0.9.10,
`@eslint/js` 10.0.1, `@types/node` 24.13.3, `@types/react` 19.2.18,
`@types/react-dom` 19.2.4, `@vitejs/plugin-react` 6.0.5, `concurrently`
9.2.4, `eslint` 10.8.1, `eslint-plugin-react-hooks` 7.1.1,
`eslint-plugin-react-refresh` 0.5.3, `globals` 17.9.0, `prettier` 3.9.6,
`prettier-plugin-astro` 0.14.1, `prettier-plugin-tailwindcss` 0.8.1,
`typescript-eslint` 8.66.0, `vite` 8.2.1, dan `vitest` 4.1.10.
TypeScript 6.0.3 berlisensi Apache-2.0.

## F. Runtime, browser, data, dan tool pemaketan

| Komponen | Kedudukan | Lisensi/ketentuan |
|---|---|---|
| Python 3.12+ | Runtime aplikasi | PSF-2.0; notice bawaan Python tetap berlaku |
| SQLite | Basis data append-only melalui Python stdlib | Public domain |
| Chromium Playwright | Browser yang dapat dibundel | BSD-3-Clause beserta banyak third-party notices |
| Tesseract OCR | Kapabilitas OCR opsional | Apache-2.0 |
| Node.js 22.13+ | Tool build frontend | MIT beserta third-party notices |
| pnpm 11.3.0 | Package manager JavaScript | MIT |
| uv | Resolver dan runner Python | Apache-2.0 OR MIT |
| Inno Setup | Pembuat installer Windows | Lisensi permisif khusus Inno Setup |

## G. Ringkasan graf dependensi produksi JavaScript

Audit `pnpm licenses list --prod --json` pada snapshot ini menghasilkan 497
record nama paket: MIT 430; ISC 24; BSD-2-Clause 12; BSD-3-Clause 8;
Apache-2.0 8; BlueOak-1.0.0 5; OFL-1.1 3; MPL-2.0 2; serta masing-masing
satu record Apache-2.0 AND LGPL-3.0-or-later, CC-BY-4.0, CC0-1.0,
Python-2.0, dan 0BSD.

Komponen dengan kewajiban notice khusus yang terdeteksi mencakup font
Fontsource (OFL-1.1), `@img/sharp-win32-x64` 0.35.3
(Apache-2.0 AND LGPL-3.0-or-later), `lightningcss` beserta binary Windows
(MPL-2.0), `caniuse-lite` (CC-BY-4.0), dan `mdn-data` (CC0-1.0).

## H. Prosedur kepatuhan

1. Gunakan hanya versi yang terkunci di `uv.lock` dan `pnpm-lock.yaml`.
2. Regenerasi inventaris ketika salah satu lockfile berubah.
3. Pertahankan `LICENSE`, `THIRD_PARTY_NOTICES.md`, serta license/notice upstream
   yang berlaku pada wheel, portable ZIP, installer, container, dan website.
4. Periksa isi nyata setiap format distribusi; paket yang ada di lockfile belum
   tentu ikut di semua format.
5. Jangan mengubah atribusi, merek, atau lisensi aset pihak ketiga menjadi MIT.
6. Catat versi, tanggal, dan hash artefak pada setiap rilis.

Hasil rinci dan aturan redistribusi tersimpan pada `THIRD_PARTY_NOTICES.md` di
akar repositori. Inventaris ini selesai untuk snapshot 13 Agustus 2026; perubahan
dependensi setelah tanggal tersebut memerlukan audit ulang.
