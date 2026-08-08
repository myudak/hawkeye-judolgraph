# BAB 7 - Implementasi Perangkat Lunak

> **Status dokumen:** source Markdown proposal. Bab ini memetakan desain pada BAB 6 ke
> implementasi MVP yang dapat dijalankan secara lokal. Angka hasil pengujian harus disesuaikan
> dengan snapshot verifikasi terbaru sebelum dokumen final diekspor.

## 7.1 Lingkup implementasi

Implementasi JudolGraph / HAWK-EYE terdiri dari dua jalur yang saling melengkapi:

1. **Evidence core** untuk menangkap halaman publik, menyimpan artefak, mengekstrak observasi,
   dan membangun graph dasar secara deterministik.
2. **Investigator workspace** untuk menjalankan fixture interaksi, menghubungkan event dengan
   graph progresif, menampilkan screenshot dan timeline, serta melakukan approval dan human review
   secara lokal.

Keduanya berada dalam satu paket Python `hawkeye`. Aplikasi web menggunakan FastAPI dan aset
frontend vanilla JavaScript tanpa dependensi runtime remote. Server hanya bind ke loopback. Target
live bersifat opt-in; regression truth menggunakan fixture lokal dan artefak yang memiliki hash.

## 7.2 Struktur modul

| Area | Modul utama | Peran implementasi |
|---|---|---|
| Command line | `hawkeye/cli.py`, `hawkeye/__main__.py` | Menyediakan subcommand `investigate`, `serve`, `benchmark`, `codex-probe`, `diagnose`, `evaluate`, dan `demo` |
| Model domain | `hawkeye/models.py` | Pydantic model untuk capture, readiness, crawl, evidence, semantic observation, candidate, dan graph dasar |
| Safety dan crawl | `hawkeye/collector/safety.py`, `hawkeye/crawl.py`, `hawkeye/pipeline.py` | Validasi URL/DNS, same-host BFS, budget, redirect, dan status failure |
| Browser capture | `hawkeye/collector/playwright_collector.py` | Render satu halaman dengan Playwright, checkpoint, screenshot, response metadata, dan blocked request |
| Extraction | `hawkeye/extraction/`, `hawkeye/semantic_evidence.py` | Ekstraksi entity lama dan typed public semantic observation dengan provenance |
| Interaction | `hawkeye/interaction/` | Stable reference, fixture scenario, preflight policy, dan executor read-only |
| Agent | `hawkeye/agent/` | Capability probe, strict JSON decision, exact reference validation, retry, dan fallback |
| Investigation runtime | `hawkeye/investigation/` | Event, lead, assertion, review, fixture/live runtime, dan reducer graph |
| Storage | `hawkeye/storage/`, `hawkeye/investigation/store.py` | File artifacts, manifest/hash, SQLite append-only history |
| Local console | `hawkeye/review_app/` | FastAPI API, workspace projection, canvas, minimap, inspector, timeline, replay, dan review controls |
| Evaluation | `hawkeye/evaluation/`, `hawkeye/benchmark.py` | Manifest verifier, three-mode benchmark, policy metrics, dan report |

Pemisahan ini membuat perubahan pada tampilan tidak mengubah event truth, dan membuat test
collector atau policy dapat dijalankan tanpa membuka UI.

## 7.3 Jalur implementasi capture

### 7.3.1 Validasi seed dan batas jaringan

`SafetyPolicy` menerima URL HTTP(S) publik, menormalisasi hostname IDN, memeriksa alamat privat,
loopback, kredensial URL, dan tujuan redirect. `pipeline.investigate` kemudian membuat case baru
dan konfigurasi dengan batas yang dapat diaudit:

- maksimal 5 halaman HTML dan depth 1 untuk same-host BFS;
- maksimal 5 redirect per halaman;
- timeout halaman maksimal 30 detik dan timeout case maksimal 120 detik;
- maksimal 200 request browser dan response terdeklarasi 10 MB;
- HTML maksimum 5 MB untuk persistence;
- satu halaman browser aktif pada satu waktu.

Link eksternal dapat dicatat sebagai observasi atau candidate lead, tetapi tidak otomatis diikuti.
Kegagalan child page dipersist sehingga tidak menghapus hasil halaman lain dalam case yang sama.

### 7.3.2 Checkpoint dan pemilihan capture canonical

`BrowserCollector` menyimpan checkpoint pada 0, 500, 1500, dan 3000 ms. Jika indikator masih
berubah, collector dapat melakukan settle extension pada 5000 dan 8000 ms dalam budget yang sama.
Setiap checkpoint mencatat antara lain:

- ready state, ukuran HTML, visible text, element/link/button/image count;
- document width/height dan metrik informasi screenshot;
- SHA-256, ukuran, dan dimensi screenshot.

Delta antar checkpoint dihitung untuk mendeteksi render terlambat. Classifier memisahkan empat
dimensi yang sebelumnya mudah tercampur:

```text
navigation result
    -> access outcome
    -> capture adequacy
    -> extraction eligibility
    -> public-facing status
```

Dengan demikian, HTTP berhasil tidak otomatis berarti evidence memadai. Capture dapat berstatus
`captured_with_limitations`, `access_challenge_observed`, `geo_restriction_observed`, atau
`collection_failed` dengan alasan yang tersimpan.

### 7.3.3 Artefak yang disimpan

Filesystem case menyimpan HTML bila berada di bawah limit, visible text, response/redirect metadata,
canonical viewport screenshot, initial screenshot saat tersedia, dan bounded full-page screenshot.
Full-page capture dibatasi pada tinggi 12.000 px. Jika HTML terlalu besar atau full-page tidak dapat
dibuat, alasan omission disimpan pada readiness, bukan diganti dengan placeholder yang tampak valid.

Setiap file memiliki stable evidence ID, media type, source page, waktu, byte size, dan SHA-256.
Case loader memverifikasi manifest dan hash sebelum artifact dikirim ke UI.

## 7.4 Implementasi semantic evidence

`extract_semantic_observations` membaca HTML yang eligible/provisional menggunakan BeautifulSoup
dan mengembalikan observasi bertipe. Tipe yang saat ini didukung adalah:

```text
claimed_brand_identity
public_telegram_alias
public_telegram_contact
public_whatsapp_link
public_phone_number
public_email_address
public_outgoing_link
public_redirect_target
public_download_destination
public_payment_method
public_payment_provider
public_offer_claim
public_legal_or_license_claim
public_referral_code
public_tracking_identifier
```

Setiap `SemanticObservation` mempertahankan raw value, normalized value, source page, source URL,
source artifact, selector atau konteks, screenshot evidence ID, confidence, extraction method,
evidence strength, dan attributes. Normalisasi tidak menghapus raw value sehingga reviewer dapat
membandingkan hasil aturan dengan halaman sumber.

Extractor menggunakan deduplikasi bertipe dan batas maksimum observasi per halaman. Selector dan
crop bersifat best-effort: crop hanya dilampirkan bila elemen dapat dicocokkan dengan snapshot
viewport yang stabil. Tidak ada klaim OCR gambar pada implementasi ini; teks visual yang tidak ada
di DOM dapat tetap menjadi limitation.

## 7.5 Implementasi controlled interaction

### 7.5.1 Scenario manifest

Sepuluh fixture interaksi disimpan dalam
`evaluation/fixtures/controlled-interactions-v1.json`. Setiap scenario mendeskripsikan seed
`.invalid`, observasi awal, stable elements, expected observable, expected candidate/relation, dan
unsafe control IDs. Fixture tidak menghubungi internet dan menjadi sumber kebenaran untuk benchmark.

### 7.5.2 Stable reference dan policy

`StableElementReference` mengikat reference ID ke snapshot ID, element ID, DOM path, role, label,
href, action, dan fingerprint. Executor menolak reference yang stale atau tidak cocok dengan
snapshot. `InteractionBudget` membatasi iterasi, interaksi, halaman, depth, redirect, query,
candidate page, dan runtime.

Preflight server-side membaca tag, role, accessible name, href/action, form owner, download,
new-tab, declared behavior, destination scheme, dan keyword risk. Login/register, submit form,
komunikasi, payment/betting, download, unsafe scheme, external application, serta aksi ambigu
diblokir sebelum eksekusi. Block disimpan sebagai decision dengan `executed=false`.

### 7.5.3 Read-only action yang diperbolehkan

Jalur aman hanya dapat melakukan state inspection, membuka public HTTP(S) link dalam scope,
mengambil redirect chain, capture state, atau reveal fixture public evidence yang sudah dideklarasi.
Setelah aksi selesai, halaman/observasi/redirect baru ditambahkan sebagai event dan artifact; aksi
tidak pernah langsung membuat assertion final.

## 7.6 Implementasi Codex dan fallback

`CodexLbClient` hanya menerima dua endpoint loopback yang telah ditentukan:

```text
http://127.0.0.1:2455/backend-api/codex
http://127.0.0.1:2455/v1/responses
```

Client mengirim context terstruktur, schema JSON strict untuk `AgentDecision`, dan timeout maksimal
30 detik. Ia tidak memberikan browser, shell, filesystem, database, atau cookie handle kepada model.
Sebelum tool request dijalankan, `_validate_context_decision` mencocokkan seluruh reference dengan
reference yang diterbitkan server untuk snapshot yang sama.

`CodexInvestigator` melakukan paling banyak dua percobaan. Transport error, JSON/schema invalid,
atau reference mismatch dicatat sebagai `AgentFailure`; setelah batas tercapai, keputusan dialihkan
ke `DeterministicInvestigator`. Fallback merangking label publik secara sederhana, memilih satu
aksi yang lolos policy, atau mengembalikan `stop`. Kedua jalur menggunakan schema keputusan yang
sama sehingga runtime dan UI dapat menjelaskan mode `codex` versus `deterministic_fallback`.

Capability probe memisahkan tiga kondisi: route tersedia, output strict valid, dan capability siap
dipakai. Tidak tersedianya codex-lb tidak menghentikan fixture demo atau mengubah failure menjadi
success palsu.

## 7.7 Implementasi candidate, recollection, dan review

Observasi public link, redirect, iframe, new-tab, dan fixture index diproses oleh runtime menjadi
`CandidateLead`. Lead menyimpan URL, discovery method, source observation IDs, collection mode,
status awal, dan waktu. Lead yang hostname-nya sudah ada di corpus lokal dapat diproyeksikan sebagai
destination collected tanpa network collection ulang.

Lead baru tetap `waiting` atau `pending`. Endpoint approval hanya mengizinkan recollection satu
halaman Page B dengan depth nol dan budget yang sama. Candidate tidak dicrawl otomatis, dan hasil
recollection tidak langsung menjadi fakta kepemilikan.

`CandidateAssertion` menyimpan tipe relasi, subject, object, observation IDs, artifact IDs, dan
limitations. Assertion dimulai sebagai `needs_review`. Reviewer menambahkan outcome seperti
`verified`, `rejected`, `needs_more_evidence`, `duplicate`, atau `uncertain` beserta label dan alasan.

SQLite pada `hawkeye/investigation/store.py` memiliki tabel `events`, `candidate_leads`,
`assertions`, dan `reviews`. Trigger database menolak UPDATE dan DELETE, sedangkan versi review
meningkat secara append-only. Identitas reviewer pada MVP adalah label lokal, bukan authenticated
identity.

## 7.8 Event-driven graph dan workspace

Setiap event mempunyai event ID, sequence monotonic per run, case/run ID, kind, timestamp,
causation ID, correlation ID, schema version, dan payload. Event kinds mencakup run, collection,
artifact, interactive, evidence gap, agent/tool, observation, entity, search lead, approval,
assertion, review, completion, dan failure.

`reduce_events` membangun `ProgressiveGraphState` secara idempotent. Reducer memproyeksikan node
seed/collected page, claimed brand, public contact/claim, external destination, redirect, dan
candidate domain. Edge appearance menunjukkan status evidence:

| Appearance | Makna pada UI |
|---|---|
| `solid` | Relasi observasi yang didukung event/artifact |
| `dashed` | Candidate atau assertion yang masih provisional |
| `solid_emphasized` | Assertion yang telah mendapat review outcome yang sesuai |
| `hidden` | Relasi ditolak atau tidak boleh ditampilkan sebagai graph fact |

Canvas, minimap, pan/zoom/drag, hit-test, search/focus, inspector, screenshot carousel, dan replay
dibangun di `hawkeye/review_app/static/`. Timeline animation hanya mengonsumsi event projection;
pause, speed, replay, refresh, dan reduced-motion tidak menambah atau menghapus event.
UI juga menyediakan tabel/inspector agar graph tidak menjadi satu-satunya cara membaca evidence.

## 7.9 API dan cara menjalankan demo lokal

Server dibuat oleh `hawkeye.review_app.create_app` dan dijalankan melalui `python -m hawkeye serve`.
Endpoint legacy membaca case filesystem secara read-only. Dengan `--workspace`, endpoint MVP
menyediakan:

```text
GET  /api/mvp/scenarios
GET  /api/mvp/capabilities
GET  /api/mvp/runs
POST /api/mvp/runs
GET  /api/mvp/runs/{workspace_id}
POST /api/mvp/runs/{workspace_id}/reviews
POST /api/mvp/runs/{workspace_id}/approve
GET  /api/mvp/runs/{workspace_id}/artifacts/{artifact_name}
```

Contoh jalur offline yang tidak memerlukan live site:

```powershell
python -m hawkeye benchmark --output verification-output/benchmark
python -m hawkeye serve --cases cases --workspace verification-output/mvp-workspace --port 8766
```

Evaluator dapat memilih fixture scenario, mengamati graph dan timeline, membuka screenshot atau
JSON evidence, mencoba review assertion, lalu mengulang run yang sama. Untuk jalur collector live,
gunakan URL publik hanya sebagai evaluasi opt-in dan simpan output di direktori ignored.

## 7.10 Verifikasi implementasi

Gate yang dipakai sebelum snapshot proposal:

| Gate | Yang diperiksa |
|---|---|
| Formatter | Konsistensi Python dengan Ruff format |
| Linter | Error E/F/I/B/UP dan import order |
| Type checker | Strict mypy pada `hawkeye` |
| Unit/integrasi | Model, safety, capture, extraction, interaction, agent, runtime, store, reducer, API |
| JavaScript syntax | `node --check hawkeye/review_app/static/app.js` |
| Integrity | Manifest, hash, stable references, append-only trigger |
| Benchmark | Sepuluh fixture pada static, rule-based, dan agent-assisted/fallback |
| Browser/local demo | UI localhost, screenshot inspector, canvas, timeline/replay, review path |
| Diff hygiene | `git diff --check` dan pemeriksaan status repository |

Snapshot repository mencatat status dan angka verifikasi pada `gemastik-2026/IMPLEMENTATION_STATUS.md`
dan `docs/STATUS.md`. Angka tersebut adalah hasil pada fixture dan lingkungan tertentu; angka live
tidak boleh dipindahkan menjadi klaim akurasi umum.

## 7.11 Keterbatasan implementasi saat ini

1. Codex path bergantung pada capability probe dan endpoint loopback; fallback tetap menjadi jalur
   yang sah bila service tidak tersedia.
2. Rule-based semantic extraction berfokus pada DOM/visible text dan link metadata; tidak ada OCR
   universal atau jaminan memahami semua canvas/image-only content.
3. Browser collector dan interaction executor memiliki budget serta same-site scope; keduanya
   bukan crawler unlimited atau computer-use agent umum.
4. Candidate, similarity, dan shared public signal bukan ownership probability. Human review wajib.
5. Review identity masih label lokal; public deployment, authentication, multi-user authorization,
   dan distributed storage belum termasuk MVP.
6. Live web berubah menurut waktu, lokasi, session, dan policy target. Fixture `.invalid` tetap
   menjadi regression truth.

## 7.12 Rujukan implementasi

- `README.md` - instalasi, command, artefak case, dan verification gates.
- `hawkeye/pipeline.py` dan `hawkeye/collector/playwright_collector.py` - capture dan crawl.
- `hawkeye/semantic_evidence.py` - typed semantic evidence.
- `hawkeye/interaction/` dan `hawkeye/agent/` - controlled interaction serta bounded Codex.
- `hawkeye/investigation/` - event store, runtime, reducer, candidate, assertion, dan review.
- `hawkeye/review_app/` - API dan console localhost.
- `evaluation/fixtures/` dan `tests/` - fixture truth dan verifikasi.
- `gemastik-2026/IMPLEMENTATION_STATUS.md` - capability map dan limitation snapshot.
