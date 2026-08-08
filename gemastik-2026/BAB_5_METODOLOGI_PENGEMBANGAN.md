# BAB 5 - Metodologi Pengembangan Perangkat Lunak

> **Status dokumen:** source Markdown proposal. Nama produk, identitas tim, institusi, pembimbing,
> dan metadata lomba masih harus diisi serta diverifikasi oleh manusia.

## 5.1 Pendekatan pengembangan

JudolGraph / HAWK-EYE dikembangkan dengan pendekatan **iterative-incremental** yang berorientasi
pada bukti (*evidence-driven*). Pendekatan ini dipilih karena masalah yang diselesaikan bukan hanya
membuat crawler, tetapi juga memastikan bahwa setiap hasil dapat ditelusuri, dibatasi, diuji, dan
ditafsirkan secara hati-hati.

Tim tidak mengklaim menggunakan Scrum formal dengan peran, jadwal sprint, atau artefak organisasi
yang belum terdokumentasi. Istilah yang digunakan dalam proposal ini adalah *milestone* dan
*iterasi teknis*: setiap iterasi mempunyai tujuan, batas keselamatan, acceptance criteria, fixture
atau data verifikasi, keputusan desain, serta catatan keterbatasan.

Siklus dasar setiap iterasi adalah:

```text
Identifikasi masalah
        -> kebutuhan terukur
        -> desain dan keputusan batas
        -> implementasi terkecil yang dapat diuji
        -> pengujian fixture/regresi
        -> demo atau evaluasi opt-in
        -> review bukti dan keterbatasan
        -> iterasi perbaikan berikutnya
```

Siklus tersebut menjaga agar perubahan pada collector, agen, graph, atau UI tidak hanya dinilai
dari tampilan akhir. Perubahan harus dapat dikaitkan dengan kode, test, artefak, dan keputusan
arsitektur yang relevan.

## 5.2 Prinsip proses

Proses pengembangan menerapkan prinsip berikut.

1. **Bukti sebelum kesimpulan.** Artefak capture dan observasi disimpan sebelum kandidat atau
   relasi dibuat.
2. **Deterministik sebagai jalur dasar.** Collector, extractor, candidate generator, comparison,
   fixture runtime, dan fallback agen menggunakan aturan yang dapat diulang.
3. **Batas eksplisit.** Batas URL, DNS, same-site crawl, halaman, waktu, ukuran HTML, tindakan,
   dan recollection ditulis sebagai konfigurasi serta diuji sebagai perilaku.
4. **Kegagalan harus dapat dijelaskan.** Restriction, challenge, timeout, HTML besar, kegagalan
   model, tindakan terblokir, dan review yang belum selesai dipersist sebagai status atau event;
   kegagalan tidak ditutupi dengan data sintetis.
5. **Live observation bukan test truth.** Situs publik hanya digunakan secara opt-in untuk
   observasi kualitatif. Fixture lokal dan manifest evaluasi menjadi dasar regression test.
6. **Keputusan manusia tetap diperlukan.** Kandidat selalu berupa lead; assertion dimulai dari
   `needs_review` dan status terkini diturunkan dari riwayat review append-only.

## 5.3 Tahapan dan iterasi aktual

Milestone di bawah ini mencatat urutan pengembangan produk. Nama G0-G9 adalah kode internal untuk
memudahkan penelusuran bukti, bukan klaim bahwa seluruh milestone merupakan metodologi organisasi
formal.

| Iterasi | Fokus | Hasil yang ditargetkan | Bukti validasi |
|---|---|---|---|
| V0-V1 | Seed, safety, capture, extraction, graph dasar, dan console localhost | Jalur minimum dari URL publik ke artefak dan graph | Test collector, safety, extraction, graph, serta baseline tag |
| G0 | Governance dan evaluasi reproducible | Aturan permanen, fixture policy, manifest live opt-in, dan evaluator read-only | Dokumen `docs/`, manifest evaluasi, dan verifier lokal |
| G1 | Capture-readiness diagnostics | Checkpoint pengukuran untuk shell yang terlambat render tanpa mengubah capture canonical | Delapan skenario fixture diagnostik dan `hawkeye diagnose` |
| G2 | Workflow investigator | Narasi kasus, provenance, tabel relasi, bahasa lead yang netral, dan demo offline | UI/API test serta demo sanitized |
| G3 | Paket demonstrasi | Label fixture hash-backed, threat model, evaluator guide, dan storyboard | Verifier G3 fail-closed dan laporan lokal |
| G4A | Capture adequacy | Checkpoint 0/500/1500/3000 ms, settle terbatas, screenshot awal/kanonik/full-page, status akses dan kecukupan | `tests/test_capture_adequacy.py` dan fixture capture |
| G4B | Semantic evidence | Observasi bertipe dengan nilai raw/normalized, provenance, konteks, dan crop best-effort | `tests/test_semantic_evidence.py` |
| G5 | Controlled safe expansion | Sepuluh skenario interaksi, stable references, tool sempit, dan server policy preflight | `tests/test_controlled_interaction.py` dan benchmark fixture |
| G6 | Bounded Codex runtime | Capability probe, strict structured output, exact reference validation, bounded retry, dan fallback | `tests/test_agent_runtime.py`, capability JSON, dan benchmark |
| G7 | Candidate recollection dan review | Lead, approval boundary, recollection Page B, assertion evidence-backed, SQLite append-only | Runtime/review tests dan approval walkthrough |
| G8 | Event-driven graph dan evaluasi | Event monotonic, reducer idempoten, animation terpisah, replay, dan tiga mode benchmark | `tests/test_investigation_runtime.py`, reducer tests, benchmark JSON |
| G9 | Paket GEMASTIK | Proposal, technical document, video script, matrix klaim, lisensi, originality draft, dan checklist | Folder `gemastik-2026/` serta figure index |

Setiap baris diperlakukan sebagai increment yang dapat dipresentasikan secara mandiri. Jika suatu
iterasi menemukan defect, perubahan dilakukan pada fixture atau reproducer lokal terlebih dahulu.
Observasi Chrome dan situs live hanya menjadi catatan perbandingan, bukan dasar untuk mengubah
perilaku collector tanpa reproducer yang aman.

## 5.4 Alur kerja satu perubahan fitur

Untuk fitur baru, tim menggunakan alur berikut.

### 5.4.1 Perumusan masalah dan kebutuhan

Masalah ditulis sebagai perilaku yang dapat diamati, misalnya: "capture berhasil tetapi screenshot
masih kosong pada checkpoint awal" atau "tombol Contact berisi bukti publik yang belum muncul".
Kebutuhan kemudian dipisahkan menjadi:

- perilaku yang harus ada;
- perilaku yang harus diblokir;
- artefak/provenance yang wajib disimpan;
- status ketidakpastian yang harus terlihat;
- acceptance criteria yang dapat diuji tanpa internet.

### 5.4.2 Desain dan keputusan batas

Desain ditulis dalam ADR dan dokumen scope sebelum implementasi besar. Contohnya adalah pemisahan
`navigation_status`, `access_outcome`, `capture_adequacy`, dan `extraction_eligible`; larangan
candidate-domain crawl otomatis; serta keputusan bahwa animation queue tidak boleh menjadi sumber
kebenaran graph.

### 5.4.3 Implementasi incremental

Implementasi dimulai dari fungsi deterministik terkecil. Model data, storage, collector, policy,
runtime, reducer, dan UI dihubungkan setelah kontrak masing-masing dapat diuji. Agen Codex hanya
menerima context terstruktur dan harus mengembalikan `AgentDecision`; ia tidak menerima Playwright
mentah, shell, database, atau filesystem handle.

### 5.4.4 Pengujian dan verifikasi

Setiap perubahan melewati test yang paling dekat dengan failure mode, kemudian regression test yang
lebih luas. Untuk UI, API response, DOM yang dapat diakses, canvas, screenshot, dan console log
diperiksa sebagai bukti yang berbeda. Untuk live capture, artefak disimpan di direktori ignored dan
case loader memverifikasi hash serta referensi sebelum data ditampilkan.

### 5.4.5 Review dan keputusan iterasi

Hasil test, limitation, dan perubahan scope dicatat. Jika bukti tidak cukup, status tetap
`pending`, `limited`, atau `needs_review`. Fitur baru tidak boleh memperluas klaim menjadi
ownership, operator, kriminalitas, atau probabilitas hubungan.

## 5.5 Strategi pengujian dan validasi

| Lapisan | Tujuan | Contoh artefak atau test |
|---|---|---|
| Unit | Memeriksa fungsi lokal dan model | Normalisasi URL, extractor, classification, policy, model validation |
| Integrasi | Memeriksa kontrak antar modul | Pipeline capture, loader integrity, workspace API, SQLite store |
| Fixture interaction | Memeriksa tindakan aman dan terlarang | Sepuluh fixture: visible evidence, modal, menu, tab, iframe, redirect/new tab, ambiguous, login/register, download, no useful hidden evidence |
| Regression | Menjaga perilaku milestone lama | Frozen G2/G3 verifier, manifest hash, evaluator report |
| Benchmark | Membandingkan static, rule-based, dan agent-assisted fallback | `raw-results.json`, `BENCHMARK_RESULTS.md`, recall/task success/policy safety |
| UI/manual | Memastikan jalur judge dapat digunakan | Localhost walkthrough, DOM accessibility, canvas interaction, screenshot inspector, timeline/replay |
| Live qualitative | Menguji robustness secara opt-in | Manifest URL, catatan lingkungan, raw case ignored; tidak masuk CI truth |

Gate teknis sebelum milestone dinyatakan selesai adalah formatter, linter, type checker, test
relevan atau full suite, JavaScript syntax check, `git diff --check`, dan satu demonstrasi lokal
yang dapat diulang. Output command dan tanggal verifikasi disimpan di status package; angka tidak
dipindahkan ke proposal sebagai klaim permanen apabila hanya berasal dari live site.

## 5.6 Evaluasi dan umpan balik

Evaluasi menggunakan tiga mode pada fixture yang sama:

1. **Static** untuk menunjukkan batas tanpa interaksi;
2. **Rule-based** untuk menunjukkan perilaku deterministic safe fallback;
3. **Agent-assisted** dengan capability gate dan deterministic fallback ketika Codex tidak tersedia
   atau output tidak lolos validasi.

Perbedaan mode dibaca sebagai perbedaan coverage/task behavior pada fixture, bukan sebagai ukuran
kecerdasan model atau akurasi live-web. Umpan balik dari evaluasi dipetakan ke jenis perubahan:

- defect correctness -> tambah/reduksi fixture dan regression test;
- defect safety -> perketat policy preflight dan negative test;
- defect provenance -> tambah artifact/event reference;
- defect usability -> perbaiki layout, label, keyboard path, atau inspector tanpa mengubah graph truth;
- defect scope -> tulis ADR dan perbarui limitation sebelum menambah fitur.

## 5.7 Manajemen risiko pengembangan

| Risiko | Deteksi | Respons proses |
|---|---|---|
| DOM berubah setelah capture | Delta checkpoint, screenshot, dan readiness | Label `limited`/provisional; tambah fixture delayed-render |
| Model mengeluarkan tool reference tidak sah | Strict schema dan exact issued-reference validation | Catat failure, aktifkan fallback, jangan eksekusi |
| Kandidat dianggap fakta | Status `pending`, dashed edge, review history | Perbaiki wording dan provenance; tidak menaikkan klaim |
| UI animation menyimpang dari event | Replay/reducer comparison | Event menjadi sumber truth; animation queue dipisah |
| Live site berbeda menurut waktu/lokasi | Manifest dan catatan lingkungan | Jangan jadikan CI truth; gunakan reproducer lokal |
| Perubahan merusak milestone lama | Full regression/frozen verifier | Tahan perubahan atau dokumentasikan ADR dan migration |

## 5.8 Definition of done untuk proposal

Satu increment dinyatakan siap masuk paket GEMASTIK jika:

- kebutuhan dan batasnya dapat dibaca tanpa melihat source code;
- ada implementasi yang dapat dijalankan di localhost atau fixture;
- ada test atau report yang memverifikasi perilaku utama dan negative path;
- artefak/event yang ditampilkan memiliki provenance;
- limitation dan status implementasi ditulis secara jujur;
- demo dapat diulang dari command yang terdokumentasi;
- klaimnya tidak melampaui bukti.

Definition of done ini juga mencegah proposal hanya berisi daftar teknologi. Yang ditunjukkan kepada
juri adalah hubungan **kebutuhan -> desain -> implementasi -> pengujian -> bukti**.

## 5.9 Keterbatasan dan pekerjaan manusia

Dokumen ini tidak mengklaim adanya survei pengguna, jumlah investigator yang diuji, penghematan
waktu, dampak nasional, atau sustainability finansial. Data tersebut harus diisi hanya setelah ada
studi dan sumber yang dapat diverifikasi. Nama tim, pembimbing, institusi, deklarasi orisinalitas,
review lisensi, tanda tangan, dan pemformatan PDF resmi juga merupakan pekerjaan manusia sebelum
submission.

## 5.10 Rujukan bukti repositori

- `docs/ROADMAP.md` - batas dan acceptance milestone.
- `docs/DECISIONS.md` - ADR dan keputusan scope.
- `docs/EVALUATION.md` - protokol fixture, benchmark, dan live observation.
- `docs/STATUS.md` - status implementasi, limitation, dan snapshot verifikasi.
- `tests/` - test unit, integrasi, fixture, review, dan benchmark.
- `gemastik-2026/IMPLEMENTATION_STATUS.md` - pemetaan capability ke code, test, demo, dan limitation.
