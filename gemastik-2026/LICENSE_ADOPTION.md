# Adopsi Lisensi Perangkat Lunak

**Produk:** HAWK-EYE — JudolGraph  
**Versi:** 1.0.0  
**Tanggal berlaku:** 13 Agustus 2026

## 1. Keputusan lisensi

Perangkat lunak HAWK-EYE mengadopsi **MIT License** untuk kode sumber dan
dokumentasi yang dibuat oleh kontributor proyek. Teks lisensi lengkap ditempatkan
pada berkas `LICENSE` di akar repositori dan pengenal `MIT` dicantumkan pada
`package.json` serta `pyproject.toml`.

MIT dipilih karena sederhana, permisif, mudah diaudit, dan kompatibel dengan
sebagian besar komponen langsung yang digunakan proyek. Lisensi ini mengizinkan
penggunaan, penyalinan, perubahan, penggabungan, publikasi, distribusi,
sublisensi, dan penjualan salinan, dengan syarat pemberitahuan hak cipta dan
teks izin MIT dipertahankan pada salinan atau bagian substansial perangkat lunak.
Perangkat lunak disediakan “sebagaimana adanya”, tanpa jaminan.

## 2. Cakupan adopsi

Lisensi MIT proyek mencakup karya asli di repositori, antara lain:

- backend Python pada `apps/api/src/hawkeye`;
- antarmuka React pada `apps/web`;
- situs presentasi Astro pada `apps/marketing`;
- package internal `@hawkeye/brand`, `@hawkeye/design`, `@hawkeye/graph`, dan
  `@hawkeye/ui`;
- skrip build/evaluasi, pengujian, fixture sintetik, dan dokumentasi proyek
  sejauh haknya dimiliki kontributor proyek.

## 3. Yang tidak dilisensikan ulang sebagai MIT

Adopsi ini tidak mengubah lisensi library, font, ikon, runtime, browser, tool
build, data, logo pihak ketiga, maupun komponen lain yang haknya dimiliki pihak
lain. Komponen tersebut tetap tunduk pada lisensi upstream masing-masing.
Inventaris dan kewajiban notice dicatat dalam `THIRD_PARTY_NOTICES.md` dan
`gemastik-2026/LIBRARIES_AND_LICENSES.md`.

Materi hasil koleksi web juga bukan karya yang otomatis dilisensikan ulang oleh
proyek. Artefak koleksi digunakan sebagai bukti lokal sesuai izin, hukum, dan
ketentuan sumber yang berlaku. Paket Gemastik hanya menggunakan fixture `.invalid`
yang disanitasi; tidak menyertakan tangkapan situs judi langsung atau data pribadi.

## 4. Penerapan dalam distribusi

Setiap distribusi source, wheel, container, portable ZIP, atau installer harus:

1. menyertakan teks `LICENSE` proyek;
2. mempertahankan pemberitahuan hak cipta dan izin MIT;
3. menyertakan `THIRD_PARTY_NOTICES.md` dan teks lisensi/notice upstream yang
   berlaku pada komponen yang benar-benar didistribusikan;
4. mempertahankan kewajiban OFL, LGPL, MPL, Apache, BSD, CC, PSF, dan lisensi
   lainnya tanpa menggantinya dengan lisensi MIT proyek;
5. mendokumentasikan perubahan jika distribusi memodifikasi source proyek;
6. menjalankan audit ulang ketika `uv.lock`, `pnpm-lock.yaml`, browser bundle,
   font, OCR, atau toolchain pemaketan berubah.

Khusus distribusi Windows, pengecualian bootloader PyInstaller dan kewajiban
LGPL pystray dipertahankan. Bundle Chromium harus membawa lisensi BSD dan
third-party notices yang sesuai. Build tanpa Tesseract tidak boleh mengklaim OCR
lokal tersedia; build yang menyertakannya harus membawa notice Apache-2.0.

## 5. Hubungan lisensi dengan batas produk

Lisensi MIT adalah izin penggunaan karya, bukan jaminan akurasi hasil
investigasi dan bukan pembenaran untuk melanggar kontrol akses. HAWK-EYE tetap
dibatasi pada koleksi publik, read-only, policy-gated. Kandidat adalah lead yang
menunggu review manusia; similarity adalah kemiripan bukti, bukan probabilitas
kepemilikan; jumlah indikator adalah hitungan item bukti, bukan vonis legal.

Lisensi ini juga tidak memperluas konsol localhost menjadi layanan publik.
Autentikasi, otorisasi multi-user, deployment publik, dan threat model produksi
memerlukan keputusan terpisah.

## 6. Bukti implementasi adopsi

| Kontrol | Bukti di repositori | Status snapshot |
|---|---|---|
| Teks lisensi proyek | `LICENSE` | Diadopsi |
| Metadata JavaScript | `package.json` → `license: MIT` | Diadopsi |
| Metadata Python | `pyproject.toml` → `license = "MIT"` | Diadopsi |
| Inventaris komponen | `gemastik-2026/LIBRARIES_AND_LICENSES.md` | Selesai |
| Notice pihak ketiga | `THIRD_PARTY_NOTICES.md` | Selesai untuk lock snapshot |
| Rekam keputusan | `docs/DECISIONS.md`, ADR-038 | Selesai |

## 7. Pernyataan adopsi

Mulai 13 Agustus 2026, HAWK-EYE versi 1.0.0 menggunakan MIT License untuk
karya asli proyek, dengan seluruh lisensi dan notice pihak ketiga tetap berlaku
secara independen. Identitas dan tanda tangan pihak yang berwenang, apabila
diminta panitia, dilengkapi oleh ketua tim pada berkas pernyataan resmi.
