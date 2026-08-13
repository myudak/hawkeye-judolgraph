---
name: gemastik-writing
description: Draft, rewrite, review, and edit GEMASTIK technical proposals using concise, evidence-first Indonesian technical writing. Use especially for GEMASTIK Software Development proposals and reports.
---

# GEMASTIK Technical Writing Skill

## Purpose

Use this skill when drafting, rewriting, reviewing, or editing documents for GEMASTIK, especially the **Pengembangan Perangkat Lunak (Software Development)** category.

The goal is to produce writing that is:

* clear,
* concise,
* technically precise,
* evidence-driven,
* easy for judges to scan,
* consistent with GEMASTIK requirements,
* free from AI-like academic filler,
* explicit about what is implemented, measured, planned, or inferred.

Treat a GEMASTIK proposal as an **evidence-first engineering document**, not as a marketing pitch and not as a miniature undergraduate thesis.

---

## Core Principle

Write using this default reasoning pattern:

> **Claim → Evidence → Explanation → Implication**

Every important claim should answer:

1. What is being claimed?
2. What evidence supports it?
3. What does the evidence mean?
4. Why does it matter for the proposed system?

Do not substitute adjectives for evidence.

Bad:

> HAWK-EYE merupakan solusi inovatif dan komprehensif yang dapat membantu investigasi judi daring secara efektif.

Better:

> HAWK-EYE membantu analis menelusuri hubungan antarbukti pada situs judi daring. Sistem menyimpan artefak hasil pengumpulan data, mengekstrak observasi yang dapat diverifikasi, lalu menyajikan hubungan tersebut dalam *evidence graph*. Setiap hubungan tetap memerlukan peninjauan manusia sebelum digunakan sebagai dasar interpretasi.

---

# 1. Priority Order

When rules conflict, follow this priority:

1. Official GEMASTIK requirements.
2. GEMASTIK judging criteria.
3. Facts and evidence from the project.
4. Scientific and technical accuracy.
5. This writing style.
6. General academic-writing conventions.

Never change a technically correct statement merely to make it sound more academic.

Never sacrifice clarity for formality.

---

# 2. Write for the Rubric

Every substantial section should contribute to at least one judging criterion.

For Software Development, pay particular attention to:

* urgency of the problem,
* innovation,
* measurable impact,
* sustainability,
* UI, usability, and UX,
* development process,
* consistency between proposed idea and implementation.

Do not spend large amounts of space on material that does not improve the judge's ability to evaluate the work.

Before keeping a paragraph, ask:

> What does this paragraph help the judge evaluate?

If the answer is unclear, shorten it, move it, or delete it.

---

# 3. Put the Main Point First

Start paragraphs with the information the reader needs most.

Prefer:

> Pengumpulan bukti dilakukan secara deterministik agar hasil investigasi dapat diperiksa ulang.

Instead of:

> Dalam proses pengembangan sistem yang dilakukan oleh tim, terdapat berbagai aspek yang perlu diperhatikan, salah satunya adalah mengenai bagaimana mekanisme pengumpulan bukti dapat dilakukan secara konsisten.

Do not make the reader search for the point.

---

# 4. One Paragraph, One Main Idea

A paragraph should normally contain one principal claim.

Recommended structure:

```text
Main claim.
Evidence or concrete mechanism.
Interpretation.
Consequence or design decision.
```

Example:

> Situs judi daring dapat mengubah antarmuka tanpa mengubah infrastruktur yang mendasarinya. Karena itu, HAWK-EYE tidak membandingkan situs hanya berdasarkan teks atau tangkapan layar. Sistem juga membandingkan atribut DOM, aset, dan indikator komunikasi yang ditemukan pada hasil pengumpulan data. Pendekatan ini membuat kemiripan dapat diperiksa melalui beberapa jenis bukti.

Do not combine unrelated architecture, UX, implementation, and impact claims into one paragraph.

---

# 5. Use Simple Indonesian

Prefer the simplest word that preserves the intended technical meaning.

Prefer:

* `menggunakan` over `memanfaatkan` when no distinction exists,
* `membuat` over `melakukan pembuatan`,
* `mengukur` over `melakukan pengukuran`,
* `mengumpulkan` over `melakukan proses pengumpulan`,
* `menyimpan` over `melakukan penyimpanan`,
* `menguji` over `melaksanakan pengujian terhadap`.

Avoid bureaucratic prose.

Bad:

> Sistem melakukan proses pengumpulan terhadap informasi yang terdapat pada halaman situs.

Better:

> Sistem mengumpulkan informasi dari halaman situs.

---

# 6. One Concept, One Term

Use one canonical term for one concept.

Once a term is defined, use it consistently.

Example canonical vocabulary:

```text
evidence graph
artefak
observasi
hubungan
collector
investigasi
kasus
seed URL
capture
bukti digital
candidate
human review
```

Do not alternate arbitrarily between:

```text
evidence graph
graf bukti
knowledge graph
relationship graph
jaringan bukti
```

unless those terms describe genuinely different concepts.

Maintain a terminology table when the project contains many domain-specific terms.

---

# 7. Prefer Active Voice

Prefer an explicit actor when the actor matters.

Prefer:

> HAWK-EYE menyimpan HTML dan tangkapan layar setiap halaman.

Instead of:

> HTML dan tangkapan layar setiap halaman kemudian dilakukan penyimpanan oleh sistem.

Passive voice is acceptable when the actor is irrelevant.

Acceptable:

> Setiap artefak diberi hash SHA-256.

The goal is clarity, not eliminating every passive construction.

---

# 8. Keep Sentences Short

Prefer sentences containing one principal idea.

As a heuristic:

* 10–25 words is usually comfortable.
* Review sentences longer than approximately 30 words.
* Split sentences when they contain multiple independent claims.

This is a readability heuristic, not an official GEMASTIK requirement.

Bad:

> Sistem kemudian melakukan proses analisis terhadap berbagai artefak yang sebelumnya telah berhasil dikumpulkan dengan menggunakan beberapa metode perbandingan yang bertujuan untuk menemukan berbagai jenis kemiripan yang mungkin dapat menunjukkan adanya hubungan tertentu.

Better:

> Sistem membandingkan artefak yang telah dikumpulkan. Perbandingan menggunakan beberapa sinyal untuk menemukan kemiripan antarsitus. Kemiripan tersebut menjadi kandidat hubungan yang kemudian ditinjau oleh pengguna.

---

# 9. Remove Academic Filler

Delete phrases that add no information.

Common examples:

```text
Pada era digital saat ini...
Seiring dengan perkembangan teknologi yang semakin pesat...
Tidak dapat dimungkiri bahwa...
Sebagaimana yang telah kita ketahui...
Pada dasarnya...
Dalam hal ini...
Adapun...
Perlu diketahui bahwa...
Pada pembahasan kali ini...
Pada bab ini akan dibahas...
Berdasarkan uraian yang telah dijelaskan sebelumnya...
Dengan demikian dapat dikatakan bahwa...
```

Use them only when they perform a real logical function.

Do not begin a section by announcing that the section exists.

Bad:

> Pada bagian ini akan dibahas mengenai arsitektur sistem HAWK-EYE.

Better:

> HAWK-EYE membagi proses investigasi menjadi tiga lapisan: pengumpulan bukti, analisis, dan peninjauan manusia.

---

# 10. Avoid Marketing Language

A GEMASTIK proposal is not a startup landing page.

Avoid unsupported terms such as:

```text
revolusioner
canggih
mutakhir
terdepan
komprehensif
powerful
cerdas
optimal
sangat efektif
sangat efisien
inovatif
unik
robust
seamless
signifikan
```

These words are allowed only when the document explains exactly what they mean and provides evidence.

Bad:

> Sistem menggunakan metode pencarian yang sangat efisien.

Better:

> Collector membatasi penelusuran pada kedalaman satu dan maksimum lima halaman per seed untuk menjaga biaya pengumpulan tetap terbatas.

Measurements beat adjectives.

---

# 11. Distinguish Status Explicitly

Never make planned functionality sound implemented.

Maintain a strict distinction between:

### Implemented

Use:

```text
menggunakan
menyimpan
menghasilkan
telah diuji
hasil pengujian menunjukkan
```

only when supported by current implementation or evidence.

### Planned

Use:

```text
akan
direncanakan
ditargetkan
akan dievaluasi
```

### Proposed

Use:

```text
diusulkan
dirancang untuk
```

### Observed

Use:

```text
pengujian menunjukkan
hasil capture menunjukkan
ditemukan
teramati
```

### Inferred

Use:

```text
mengindikasikan
diduga
menjadi kandidat
memerlukan verifikasi
```

Never turn an inference into a fact.

---

# 12. Do Not Overclaim

Especially for OSINT, security, AI, graph analysis, and classification systems.

Prefer:

> Kesamaan atribut menjadi sinyal untuk peninjauan lebih lanjut.

Instead of:

> Kesamaan atribut membuktikan bahwa kedua situs dimiliki pihak yang sama.

Prefer:

> Sistem menemukan nomor Telegram yang sama pada dua halaman.

Instead of:

> Sistem menemukan jaringan operator judi yang sama.

State exactly what the evidence supports.

---

# 13. Evidence Before Interpretation

When reporting an experiment:

```text
Setup → Observation → Interpretation → Limitation
```

Example:

> Evaluasi collector menggunakan sepuluh domain publik. Delapan domain menghasilkan artefak yang dapat dianalisis, sedangkan dua domain tidak menghasilkan capture yang memadai karena pembatasan akses dan ukuran halaman. Hasil ini menunjukkan bahwa collector dapat menangani sebagian besar sampel evaluasi, tetapi belum dapat mengatasi seluruh mekanisme pembatasan situs.

Do not report only the successful examples.

---

# 14. Quantify When Possible

Replace vague magnitude with observable numbers.

Prefer:

> Collector menyimpan maksimum lima halaman per investigasi.

Instead of:

> Collector hanya menyimpan sejumlah kecil halaman.

Prefer:

> Pengujian dilakukan pada 10 domain.

Instead of:

> Pengujian dilakukan pada beberapa situs.

Prefer:

> Diagnostic wait diuji pada 0, 500, 1.500, dan 3.000 ms.

Instead of:

> Sistem diuji menggunakan beberapa waktu tunggu.

---

# 15. Do Not Invent Precision

Measurements must come from actual project data.

Never invent:

* percentages,
* accuracy,
* performance,
* user counts,
* latency,
* effectiveness,
* survey results,
* benchmark values,
* economic impact,
* adoption projections.

If measurement is unavailable, say so.

Example:

> Dampak terhadap waktu investigasi belum diukur pada pengguna eksternal.

This is better than fabricating a percentage improvement.

---

# 16. Explain Design Decisions

Implementation sections should explain **why**, not merely list technologies.

Bad:

> Backend menggunakan FastAPI, SQLite, Playwright, dan Pydantic.

Better:

> Collector menggunakan Playwright karena bukti perlu diperoleh setelah halaman dirender oleh browser. SQLite menyimpan metadata kasus secara lokal, sedangkan artefak berukuran besar disimpan pada sistem berkas. Pemisahan ini menjaga metadata tetap mudah dikueri tanpa memasukkan seluruh artefak ke basis data.

A technology stack is not an architecture explanation.

---

# 17. Problem → Requirement → Design

Whenever possible, connect technical decisions back to the problem.

Use:

```text
Problem
↓
Requirement
↓
Design decision
↓
Implementation
↓
Evidence
```

Example:

> Konten situs dapat berubah setelah proses investigasi. Karena itu, bukti harus dapat diperiksa berdasarkan kondisi saat pengumpulan. HAWK-EYE menyimpan HTML, screenshot, metadata, dan hash artefak pada setiap capture. Investigator kemudian dapat meninjau artefak tersebut tanpa bergantung pada kondisi situs saat ini.

This pattern is preferred over isolated feature descriptions.

---

# 18. Describe Architecture as Responsibilities

Do not describe architecture only as boxes and arrows.

For each component explain:

```text
Responsibility
Input
Processing
Output
Boundary
Failure condition when relevant
```

Example:

### Collector

Responsibility:
Collect bounded public web evidence.

Input:
Validated seed URL.

Processing:
Browser navigation, bounded traversal, artifact capture.

Output:
HTML, screenshots, metadata, frontier records.

Boundary:
The collector does not authenticate, bypass CAPTCHA, or infer relationships.

---

# 19. Figures Must Carry an Argument

Do not insert figures merely as decoration.

Before a figure, explain what the reader should notice.

After a figure, explain its significance.

Preferred:

> Gambar 6 menunjukkan pemisahan antara pengumpulan bukti dan analisis. Pemisahan ini memastikan proses analisis tidak mengubah artefak asli yang telah dikumpulkan.

Avoid:

> Berikut merupakan arsitektur sistem HAWK-EYE.

Then a figure with no interpretation.

---

# 20. Tables Are for Comparison

Prefer tables when the reader must compare multiple objects across the same dimensions.

Good uses:

* competitor comparison,
* feature comparison,
* evaluation results,
* requirements,
* test cases,
* architecture alternatives,
* implementation status,
* risk analysis.

Do not convert narrative text into a table when there is no useful comparison.

---

# 21. Literature Must Have a Job

Do not cite papers only to make the proposal appear academic.

Each source should support at least one of:

```text
problem existence
problem magnitude
technical method
design rationale
evaluation method
comparison baseline
known limitation
```

After citing related work, state why it matters to this project.

Weak:

> Graph telah digunakan dalam berbagai penelitian [8].

Better:

> Studi X menggunakan graf untuk merepresentasikan hubungan antarentitas [8]. Pendekatan tersebut mendukung penggunaan graf sebagai representasi hubungan, tetapi tidak menyediakan mekanisme provenance artefak yang dibutuhkan HAWK-EYE.

---

# 22. Comparison Must Be Explicit

When claiming novelty, compare against alternatives along concrete dimensions.

Avoid:

> HAWK-EYE berbeda dengan platform lain karena menggunakan evidence graph.

Prefer a comparison across dimensions such as:

```text
automatic capture
artifact preservation
relationship representation
human review
provenance
repeatability
bounded collection
local evidence inspection
```

Novelty should emerge from the comparison.

Do not simply declare novelty.

---

# 23. Impact Must Be Measurable

Separate:

```text
Potential impact
Observed impact
Measured impact
```

Do not present potential impact as measured impact.

Example:

> HAWK-EYE berpotensi mengurangi pekerjaan manual saat menghubungkan bukti lintas situs. Pada tahap penyisihan, manfaat tersebut belum diukur melalui studi pengguna sehingga klaim efisiensi belum dapat dikuantifikasi.

Whenever impact has been measured, report:

```text
metric
baseline
method
sample
result
limitation
```

---

# 24. Limitations Increase Credibility

State meaningful limitations explicitly.

Examples:

```text
Situs yang membutuhkan autentikasi berada di luar cakupan collector.
Challenge anti-bot dapat menghasilkan capture yang tidak memadai.
Hubungan pada graph tidak menyatakan kepemilikan.
Hasil similarity berfungsi sebagai kandidat untuk human review.
Pengujian saat ini belum mengukur performa pada skala nasional.
```

Do not hide limitations behind vague wording.

A limitation is not automatically a weakness. It defines what the system actually guarantees.

---

# 25. Avoid Fake Transitions

Do not mechanically begin paragraphs with:

```text
Selain itu,
Selanjutnya,
Kemudian,
Di sisi lain,
Lebih lanjut,
Oleh karena itu,
```

Use transitions only when the logical relationship requires them.

A coherent argument should not depend on transition filler.

---

# 26. Avoid Repetition

Do not explain the same system feature in multiple chapters unless the context changes.

Preferred division:

```text
Problem chapter:
why the capability is needed

Design chapter:
how it is designed

Implementation chapter:
how it is built

Evaluation chapter:
whether it works
```

Cross-reference earlier sections instead of rewriting them.

---

# 27. Use Lists Only for Real Sets

Use prose for arguments.

Use bullets for:

* requirements,
* components,
* steps,
* constraints,
* deliverables,
* criteria.

Do not turn every paragraph into bullet points.

---

# 28. Define Abbreviations Once

At first meaningful use:

> Application Programming Interface (API)

Then use:

> API

Do not repeatedly redefine common terms.

Do not introduce abbreviations that appear only once or twice.

---

# 29. Preserve Technical Terms When Translation Hurts Precision

Use Indonesian prose, but retain established technical terms when they are clearer.

Acceptable:

```text
seed URL
collector
capture
evidence graph
human review
frontier
hash
browser
crawler
artifact
canonical URL
```

Italicize foreign terms if required by the document's typography convention, but prioritize consistency.

Do not create unnatural translations solely to avoid English.

---

# 30. Match Tense to Evidence

For existing system behavior:

> Sistem menyimpan...

For completed experiments:

> Pengujian menunjukkan...

For planned work:

> Tahap berikutnya akan mengevaluasi...

Avoid shifting tense inside the same status description.

---

# 31. Citation Discipline

Use a citation when a statement depends on external knowledge.

Examples requiring citations:

```text
statistics
laws or regulations
previous research
definitions from literature
claims about existing products
technical findings from other authors
```

Project-specific facts generally require internal evidence rather than academic citations.

Do not attach one citation to a paragraph containing several unrelated external claims.

Place the citation near the claim it supports.

---

# 32. Never Cite a Source You Did Not Verify

Do not fabricate:

* authors,
* titles,
* years,
* DOI,
* URLs,
* journal names,
* page numbers.

If citation metadata is uncertain, mark it for verification instead of guessing.

---

# 33. Prefer Primary Sources

For technical claims, prioritize:

1. research papers,
2. standards,
3. official documentation,
4. official statistics,
5. official regulations.

Use secondary sources when they provide relevant synthesis or when primary evidence is unavailable.

Avoid blogs as the main support for scientific claims when stronger sources exist.

---

# 34. Writing Numbers

Prefer exact and consistent notation.

Examples:

```text
10 domain
5 halaman
3.000 ms
2 MB
SHA-256
16 × 16
```

Use the same formatting convention throughout the document.

Do not alternate between:

```text
3000 ms
3,000 ms
3.000 ms
3 detik
```

without reason.

---

# 35. Headings Must Describe Content

Prefer:

```text
6.2 Arsitektur Pengumpulan Bukti
6.3 Penyimpanan Artefak
6.4 Analisis Kemiripan
```

Avoid vague headings such as:

```text
Pembahasan Sistem
Penjelasan Sistem
Fitur-Fitur
Lain-Lain
```

A reader should understand the document structure from the table of contents.

---

# 36. No Meta-Writing

Do not tell the reader what the authors are about to write.

Avoid:

> Pada subbab berikut akan dijelaskan...

> Penulis akan membahas...

> Sebagaimana telah dibahas sebelumnya...

State the content directly.

---

# 37. No Self-Congratulation

Avoid:

```text
Tim berhasil membuat...
Tim dengan sukses mengembangkan...
Karya kami memiliki keunggulan...
```

Describe results instead.

Prefer:

> Implementasi saat ini mendukung pengumpulan hingga lima halaman per seed.

The evidence should make the achievement apparent.

---

# 38. Keep Human Review Explicit

For systems that produce candidates, classifications, similarities, or graph relationships, distinguish machine output from human conclusions.

Example:

```text
System output:
candidate relationship

Reviewer action:
inspect supporting artifacts

Final state:
reviewed / rejected / unresolved
```

Do not imply that an algorithmic score itself establishes a factual relationship.

---

# 39. Recommended Paragraph Patterns

## Problem paragraph

```text
[Problem claim].
[Evidence].
[Why existing workflow is insufficient].
[Requirement created by the problem].
```

## Related-work paragraph

```text
[What previous work does].
[Relevant evidence or capability].
[Limitation relative to this problem].
[How the proposed work differs].
```

## Design paragraph

```text
[Requirement].
[Design decision].
[Mechanism].
[Trade-off or boundary].
```

## Implementation paragraph

```text
[Implemented capability].
[How it works].
[Relevant technical detail].
[Current status or limitation].
```

## Evaluation paragraph

```text
[Test objective].
[Setup].
[Result].
[Interpretation].
[Limitation].
```

---

# 40. Recommended Section Logic

For a GEMASTIK Software Development proposal, prefer this intellectual flow even when official headings differ:

```text
Problem
↓
Evidence of problem
↓
Users / stakeholders
↓
Requirements
↓
Existing approaches
↓
Gap
↓
Proposed solution
↓
Architecture
↓
Development process
↓
Implementation
↓
Evaluation
↓
Impact
↓
Limitations
↓
Next development
```

Always preserve mandatory GEMASTIK headings and formatting when supplied by the official template.

---

# 41. AI-Like Writing Detection

Rewrite passages that exhibit several of these patterns:

* excessive `tidak hanya ... tetapi juga`,
* excessive triads,
* generic opening sentences,
* repeated conclusions,
* excessive adjectives,
* unnecessary restatement,
* uniform paragraph length,
* excessive use of `selain itu`,
* abstract nouns without actors,
* claims without measurements,
* excessive em dashes,
* fake quotations,
* excessive bold formatting,
* `dalam konteks ...` used repeatedly,
* `hal ini menunjukkan pentingnya ...` without actual analysis.

AI-like writing often contains grammatically valid sentences that contribute little information.

Optimize for **information density**, not apparent sophistication.

---

# 42. Rewrite Procedure

When asked to rewrite GEMASTIK content:

### Step 1 — Identify the purpose

Classify each paragraph as one of:

```text
problem
evidence
requirement
design
implementation
evaluation
impact
limitation
comparison
background
```

### Step 2 — Extract factual claims

Determine which statements are:

```text
verified
implemented
observed
planned
inferred
unsupported
```

### Step 3 — Remove filler

Delete sentences that provide no new information.

### Step 4 — Put the claim first

Move the key statement to the beginning.

### Step 5 — Replace vague language

Convert adjectives and abstractions into mechanisms, data, or explicit limitations.

### Step 6 — Check terminology

Use canonical terms consistently.

### Step 7 — Check evidence

Ensure quantitative and external claims have support.

### Step 8 — Check overclaiming

Reduce conclusions to what the evidence actually establishes.

### Step 9 — Connect to the rubric

Ensure the paragraph helps evaluate the submission.

### Step 10 — Read for compression

Ask:

> Can this be 20% shorter without losing information?

If yes, shorten it.

---

# 43. Review Mode

When reviewing existing text, do not merely fix grammar.

Evaluate:

```text
[ ] Is the main claim obvious?
[ ] Is the paragraph necessary?
[ ] Does evidence support the claim?
[ ] Is implementation status accurate?
[ ] Are measurements real?
[ ] Are terms consistent?
[ ] Is any sentence marketing-like?
[ ] Is any sentence unnecessarily academic?
[ ] Is any causal claim unsupported?
[ ] Does the paragraph help a judging criterion?
[ ] Can the paragraph be shorter?
```

Prioritize substantive writing problems over punctuation.

---

# 44. Strict Rules

Never:

* invent evidence,
* fabricate citations,
* invent evaluation results,
* turn plans into completed work,
* imply causality from correlation,
* claim ownership from similarity,
* claim accuracy without evaluation,
* call something innovative without comparison,
* hide meaningful limitations,
* use jargon solely to sound technical,
* add introductory filler,
* pad sections to increase page count.

---

# 45. Default Tone

Use:

> formal, direct, technical, calm, evidence-oriented Indonesian.

Do not use:

> ceremonial Indonesian, bureaucratic Indonesian, startup marketing language, exaggerated academic language, or conversational slang.

The document should sound like competent engineers explaining a system to technically literate judges.

---

# 46. Compression Test

For every sentence ask:

> If this sentence disappears, what information disappears?

If the answer is:

> almost nothing,

delete it.

For every adjective ask:

> Can this be replaced by a mechanism, comparison, or measurement?

If yes, replace it.

For every technical detail ask:

> Does the judge need this detail to understand the design, evaluate the implementation, or trust the result?

If no, omit or move it to an appendix.

---

# 47. Final Quality Standard

A strong GEMASTIK paragraph should usually contain:

```text
high information density
+
specific nouns
+
clear actors
+
observable evidence
+
explicit reasoning
+
minimal filler
```

The ideal reader reaction is:

> “I understand exactly what they built, why they built it this way, what evidence supports it, and what they are not claiming.”

Not:

> “This sounds sophisticated.”

---

# 48. Final Instruction to the Agent

When writing or editing a GEMASTIK document:

1. Preserve facts.
2. Preserve official structure.
3. Improve reasoning before improving wording.
4. Prefer evidence over adjectives.
5. Prefer mechanisms over claims.
6. Prefer direct sentences over academic filler.
7. Separate implemented, observed, planned, and inferred statements.
8. Expose meaningful limitations.
9. Keep terminology consistent.
10. Optimize every section for judge comprehension and rubric coverage.

When uncertain between a sophisticated sentence and a simple precise sentence, choose the simple precise sentence.
