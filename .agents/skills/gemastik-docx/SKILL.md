---
name: gemastik-docx
description: Create, restyle, or review GEMASTIK proposal DOCX files using a conservative Indonesian academic technical-report style. Use for GEMASTIK Software Development proposal and supporting technical documents. Do not approximate the final GEMASTIK paper format; when an official GEMASTIK/IEEE template exists, use that template exactly.
---

# GEMASTIK DOCX Style Skill

## Purpose

Use this skill when creating, formatting, restyling, or visually reviewing a `.docx` document for GEMASTIK, especially **Pengembangan Perangkat Lunak / Software Development**.

This skill controls **document presentation and DOCX mechanics**, not prose quality.

Use the separate GEMASTIK writing skill for wording, reasoning, evidence, claims, citations, and paragraph content.

The visual target is:

> **A conservative Indonesian academic technical report: restrained, dense but readable, black and white, serif, single-column, prose-first, figure-friendly, and mechanically clean.**

The document must look like a manually prepared university competition proposal, not an AI-generated business report, startup deck, landing page, or marketing document.

---

# 1. Precedence

Follow this order when rules conflict:

1. Official GEMASTIK template supplied for the specific submission.
2. Official GEMASTIK technical instructions or competition guide.
3. Institution-specific mandatory template, if explicitly required.
4. This skill.

Important:

- The GEMASTIK XIX 2026 Software Development proposal rules specify structure, page limits, and deliverables, but do **not** prescribe a complete typography system for the proposal.
- Therefore, the typography below is a **house style**, not a claim that GEMASTIK officially mandates these exact values.
- If GEMASTIK later publishes a proposal template or typography requirement, that official material overrides this skill immediately.
- For the **final GEMASTIK paper**, use the actual GEMASTIK-provided IEEE template. Do not recreate or approximate IEEE formatting from memory.

---

# 2. Scope

Apply this skill to:

- proposal penyisihan,
- laporan akhir when no stricter template is supplied,
- supporting technical documentation,
- installation/use guides when a GEMASTIK-specific style is desired,
- formatting cleanup of an existing proposal.

Do not use this style for:

- pitch decks,
- posters,
- landing pages,
- promotional one-pagers,
- final IEEE papers when an official template exists.

---

# 3. Core Visual Principle

Typography should be intentionally boring.

The document should communicate:

- seriousness,
- technical clarity,
- academic familiarity,
- efficient use of page space,
- visual consistency.

Styling must never compete with the content.

Do not attempt to make the proposal look "modern" through decorative UI patterns.

---

# 4. Page Setup

Default page setup:

- Paper: **A4**
- Orientation: **Portrait**
- Width: 21.0 cm
- Height: 29.7 cm
- Margins:
  - Top: **2.5 cm**
  - Bottom: **2.5 cm**
  - Left: **2.5 cm**
  - Right: **2.5 cm**
- Header distance: approximately 1.25 cm
- Footer distance: approximately 1.25 cm
- Columns: **1**
- Body direction: left-to-right

Do not use thesis-style 4 cm binding margins unless an institution or official template explicitly requires them.

Use landscape sections only for genuinely wide tables or diagrams that would otherwise become unreadable.

A landscape section must return to portrait immediately after the wide object.

---

# 5. Font Enforcement

## Canonical font

Use **Times New Roman** throughout the document unless a semantic exception below applies.

Do not rely on Word theme inheritance.

Explicitly enforce Times New Roman in:

- `Normal`,
- `Body Text`,
- `Title`,
- `Subtitle`,
- `Heading 1`,
- `Heading 2`,
- `Heading 3`,
- `Caption`,
- list styles,
- table text,
- header/footer styles,
- TOC styles,
- references,
- hyperlinks,
- document defaults,
- linked character styles,
- every existing run after formatting,
- OOXML theme/default font references when necessary.

The generated DOCX must not silently fall back to:

- Calibri,
- Cambria,
- Aptos,
- Arial,

unless the content explicitly requires another font.

## DOCX implementation requirement

When programmatically creating or restyling a file:

1. Set the font on all relevant paragraph styles.
2. Set `w:rFonts` for ASCII, High ANSI, East Asia, and complex script where appropriate.
3. Set document defaults.
4. Patch theme major/minor Latin fonts if needed.
5. Normalize direct run-level font overrides.
6. Inspect the package for unwanted theme font names.
7. Render the document and visually verify the result.

Never assume `style.font.name = "Times New Roman"` alone is sufficient.

---

# 6. Body Text

Default body style:

- Font: **Times New Roman**
- Size: **12 pt**
- Color: **black**
- Alignment: **Justified**
- Line spacing: **1.5**
- Space before: **0 pt**
- Space after: **0 pt**
- Left indent: **0 cm**
- Right indent: **0 cm**
- First-line indent: **0.75 cm**
- Widow/orphan control: enabled when supported

Do not progressively indent normal prose because it appears under a deeper heading.

All body paragraphs use the same text column width.

Hierarchy comes from headings, not from narrowing the paragraph column.

## Paragraph exception

Do not use a first-line indent for:

- the first paragraph immediately after a heading, if the existing document consistently follows that convention,
- list items,
- captions,
- code/pseudocode,
- table cells,
- cover metadata,
- reference entries.

Choose one convention for post-heading paragraphs and apply it consistently.

Default when creating from scratch: keep the normal **0.75 cm** first-line indent even after headings.

---

# 7. Heading Hierarchy

Keep headings compact.

Do not use Word's large default blue headings.

## Heading 1

Example:

`1. Latar Belakang Ide Perangkat Lunak`

Style:

- Times New Roman
- **12 pt**
- **Bold**
- Black
- Left aligned
- Space before: **12 pt**
- Space after: **6 pt**
- Keep with next paragraph
- No first-line indent
- No underline
- No color
- No rule below
- No shaded background

## Heading 2

Example:

`6.1 Kebutuhan Fungsional`

Style:

- Times New Roman
- **12 pt**
- **Bold**
- Black
- Left aligned
- Space before: **9 pt**
- Space after: **3 pt**
- Keep with next
- No first-line indent

## Heading 3

Example:

`7.2.1 Validasi Sumber`

Style:

- Times New Roman
- **12 pt**
- **Bold Italic**
- Black
- Left aligned
- Space before: **6 pt**
- Space after: **3 pt**
- Keep with next
- No first-line indent

## Limits

Use at most **three visible heading levels** unless the source structure genuinely requires more.

Avoid giant headings such as 16–24 pt.

Avoid all-caps headings except conventional front matter such as:

- `DAFTAR ISI`
- `DAFTAR GAMBAR`
- `DAFTAR TABEL`
- `REFERENSI`

Do not manually indent headings to simulate hierarchy.

---

# 8. Numbering

Use automatic multilevel numbering when feasible.

Preferred hierarchy:

- `1.`
- `1.1`
- `1.1.1`

Do not type numbering manually if automatic numbering can be made stable.

Do not include stray punctuation copied from requirement lists in actual headings.

Example:

Bad:

`4. Batasan Perangkat Lunak yang Dikembangkan;`

Preferred:

`4. Batasan Perangkat Lunak yang Dikembangkan`

---

# 9. Cover Page

The cover must look institutional, not promotional.

Default order:

1. `PROPOSAL GEMASTIK XIX`
2. Competition/category name
3. Project title
4. University logo
5. `Dirancang oleh Tim:` or equivalent
6. Team name
7. Member names and student IDs
8. University name
9. Year

## Cover typography

- Times New Roman
- Black
- Centered
- Main labels: **14–16 pt bold**
- Project title: **14–16 pt bold**
- Member metadata: **12 pt**
- University/year: **14 pt bold** or restrained equivalent

Do not use:

- gradients,
- colored backgrounds,
- hero illustrations,
- decorative eagle graphics,
- cards,
- banners,
- slogans,
- UI mockups,
- giant project logos.

A university logo is allowed and expected when appropriate.

Keep the logo proportional and approximately **4–5 cm** tall unless the official template specifies otherwise.

Ensure the logo does not overlap text.

Use deliberate vertical spacing instead of empty paragraphs with inconsistent font sizes.

The cover occupies exactly one page.

No visible page number on the cover.

---

# 10. Front Matter

Typical front matter may include:

- Daftar Isi
- Daftar Gambar
- Daftar Tabel

## Table of Contents

Use a real Word TOC field when possible.

Requirements:

- Times New Roman
- 11–12 pt
- Black
- Dot leaders
- Right-aligned page numbers
- Correct heading levels
- No missing page numbers
- No manually typed fake TOC if a real field can be generated

Update fields before final export when possible.

If headless rendering cannot update fields reliably, materialize or refresh fields before delivery.

## Daftar Gambar and Daftar Tabel

Use real caption fields and generated lists where practical.

Do not let front matter create accidental half-empty pages.

Start the main proposal body on a **fresh page** after front matter.

---

# 11. Page Numbers

Default:

- Cover: no visible number
- Front matter: lowercase Roman numerals if the document supports clean section numbering
- Main body: Arabic numerals beginning at 1
- Position: bottom center or bottom right
- Font: Times New Roman 10–11 pt
- Black

If Roman/Arabic section numbering would make the DOCX unstable, prefer a simpler consistent Arabic scheme after the cover rather than a broken numbering system.

Page numbers must be real Word fields, not manually typed text.

---

# 12. Lists

Use prose for arguments.

Use lists for actual sets, steps, requirements, or constraints.

## Numbered/bulleted list style

- Times New Roman 12 pt
- 1.5 spacing unless density requires 1.15–1.3 inside a long procedural list
- Left indent: approximately **0.75 cm**
- Hanging indent: approximately **0.5 cm**
- No extra blank line between short list items
- Keep indentation consistent

Do not use manual spaces or tabs to align list text.

Do not nest lists more than necessary.

---

# 13. Tables

## Default principle

Use a table only when the reader benefits from comparing rows against common columns.

Good table use:

- functional requirements,
- non-functional requirements,
- technology comparison,
- technology/function mapping,
- evaluation results,
- competitor comparison,
- test matrix,
- sprint summary,
- risk matrix,
- structured datasets.

Bad table use:

- converting ordinary prose into `Label | Description`,
- one-row key-value cards,
- every feature in a separate row,
- architecture explanation that should be prose,
- visual layout.

## Table appearance

Default:

- Black text
- White background
- Plain borders
- No colored header fills
- No gradients
- No rounded cards
- No icons
- No decorative shadows
- Header row: bold
- Table caption: above the table
- Table aligned with text margins
- Avoid overly thick borders

Font:

- Default: Times New Roman **11 pt**
- Use 12 pt for short/simple tables when space allows
- Never reduce below 9.5 pt merely to force a bad table to fit

Cell alignment:

- Text cells: left aligned
- Numeric cells: align consistently
- Header: centered or left aligned depending on content
- Vertical alignment: top for paragraph-like cells

## Table density rule

A table cell must not become a mini essay.

If a table contains long paragraphs:

- shorten the cell text,
- reduce the number of columns,
- split the table,
- move explanatory prose outside the table,
- or use a landscape section.

Do not allow narrow columns that break ordinary words into fragments such as:

`Pengem-`
`bangan`

or:

`Pemben-`
`tukan`

## Multi-page table mechanics

For every table that may span pages:

- repeat the header row,
- prevent rows from splitting across pages where practical,
- keep the caption with the table,
- avoid orphaned headers,
- avoid a single row occupying multiple pages,
- test the table after rendering.

If a row is too large to fit on one page, redesign the table.

---

# 14. Figures and Screenshots

Software proposals should use figures generously when they communicate:

- architecture,
- workflow,
- system flow,
- evidence flow,
- UI state,
- evaluation result,
- graph visualization,
- user interaction.

Figures are preferred over decorative tables for visual explanation.

## Figure sizing

Default UI screenshot width:

- approximately **80–100% of text width**

Use one large screenshot per page when the UI contains small text.

Use two screenshots on one page only if both remain readable.

Do not create a gallery of tiny unreadable screenshots.

Do not stretch screenshots disproportionately.

Preserve aspect ratio.

## Figure alignment

- Center figure
- No text wrapping around figure
- Prefer inline-with-text placement for stability

## Captions

Figure caption:

- below the figure
- Times New Roman
- **11 pt**
- Italic
- Centered
- Black
- Format:

`Gambar 7. Halaman Input Seed HAWK-EYE`

Table caption:

- above the table
- Times New Roman
- **11 pt**
- Italic
- Centered
- Black
- Format:

`Tabel 3. Kebutuhan Fungsional HAWK-EYE`

Never leave captions as:

`Gambar 12.`

Every caption must be descriptive.

## Figure-caption binding

A figure and its caption are one layout unit.

Prevent:

- figure on page N and caption alone on page N+1,
- caption at the bottom of a page with figure on the next page,
- heading separated from its first figure by a page break.

Implementation:

- set the figure paragraph to `keep_with_next`,
- set caption paragraph to `keep_together`,
- use page breaks deliberately when the combined object will not fit,
- visually verify every figure/caption pair after rendering.

---

# 15. Diagrams

Diagrams must be readable at normal page zoom.

Prefer:

- clean white background,
- black/dark text,
- restrained line colors if necessary,
- consistent type size,
- sufficient resolution.

Avoid:

- dark poster-like diagram backgrounds unless the original system screenshot itself is dark,
- tiny labels,
- unnecessary visual effects,
- diagram titles embedded inside the image when a Word caption already exists.

A technical diagram may use color when color encodes actual meaning.

Do not add color merely for decoration.

---

# 16. Pseudocode and Code

Pseudocode must look different from body prose.

Default:

- Font: **Consolas** or **Courier New**
- Size: **10.5 pt**
- Alignment: left
- Line spacing: **single**
- Space before: 6 pt
- Space after: 6 pt
- Left indent: **0.75–1.0 cm**
- First-line indent: 0
- Black
- No background fill
- No code-card styling
- No syntax-highlighting colors

Use a semantic monospace exception here only.

Do not use Cardo, Calibri, or an arbitrary theme font for pseudocode.

Keep pseudocode blocks together when practical.

Do not justify code.

---

# 17. References

Unless an official citation template says otherwise:

- Times New Roman
- **11 pt**
- Single spacing within each reference
- 3–6 pt space after each entry
- Hanging indent: approximately **0.75 cm**
- Left aligned
- Black

URLs may remain clickable but should not become bright blue corporate-style hyperlinks.

Prefer black hyperlink text with restrained underline behavior.

Do not create a separate decorative bibliography layout.

`REFERENSI` is a normal major heading, not a title page.

---

# 18. Foreign and Technical Terms

Typography only:

- italicize foreign terms when required by Indonesian academic convention,
- do not italicize every technical identifier mechanically,
- do not italicize code identifiers,
- do not italicize URLs,
- keep product/library names in roman text unless grammar requires otherwise.

Examples that may remain roman:

- FastAPI
- SQLite
- Playwright
- SHA-256
- React
- Docker Compose

Terms such as *evidence graph* may be italicized consistently if the document's language convention requires it.

Consistency matters more than aggressive italicization.

---

# 19. Emphasis

Use bold sparingly.

Bold is mainly for:

- headings,
- table headers,
- short labels where structurally useful.

Do not randomly bold phrases inside body paragraphs.

Do not use colored emphasis.

Do not highlight text with yellow/colored Word highlights in a final proposal.

Use italics for:

- conventional foreign terms,
- figure/table captions,
- limited semantic emphasis when academically appropriate.

---

# 20. Whitespace and Density

The document should be dense but not cramped.

Avoid:

- 18–24 pt paragraph gaps,
- giant gaps around headings,
- empty paragraphs used as layout spacers,
- half-empty pages caused by accidental page breaks,
- excessive section breaks.

Prefer paragraph style spacing.

Use explicit page breaks only when semantically useful:

- after the cover,
- before major front-matter sections when needed,
- before the main body,
- before a large object that cannot fit cleanly,
- for deliberate chapter-like boundaries.

Do not force every Heading 1 onto a new page unless the document structure clearly benefits.

---

# 21. No Decorative Report UI

Never add the following unless an official template requires them:

- colored cards,
- callout cards,
- pill badges,
- gradient banners,
- colored section headers,
- shaded sidebars,
- decorative icons,
- large quote blocks,
- rounded boxes,
- progress bars,
- dashboard-like KPI tiles,
- cover illustrations,
- startup-style feature grids,
- colored footer bars,
- branded page backgrounds.

A GEMASTIK proposal is not a web interface.

---

# 22. No Word Default Styling

Do not ship default Microsoft Word visual styling.

Explicitly remove or override:

- blue Heading 1,
- blue Heading 2,
- Aptos/Calibri defaults,
- theme-colored hyperlinks,
- default table accent colors,
- default SmartArt-looking diagrams.

The final document should look intentionally typeset.

---

# 23. Image Quality

Before insertion:

- use original-resolution screenshots,
- avoid JPEG recompression when PNG is appropriate,
- crop irrelevant browser chrome only when doing so does not remove context,
- preserve UI readability.

The final PDF must remain within GEMASTIK file-size limits.

If compression is required:

1. resize images to the actual display size,
2. use sensible PNG/JPEG compression,
3. do not destroy text readability,
4. render again after compression.

---

# 24. Accessibility and Robustness

Where supported:

- mark table header rows,
- add concise alt text to meaningful figures,
- use actual headings rather than manual bold paragraphs,
- use actual lists,
- use actual caption styles,
- use real page-number fields,
- use real TOC fields,
- preserve reading order.

Do not sacrifice visual correctness for unnecessary structural complexity.

---

# 25. DOCX Construction Rules

When using `python-docx` or OOXML:

- use integer Word measurements,
- avoid malformed decimal twip values,
- do not construct layout through repeated spaces,
- do not use floating images unless absolutely required,
- prefer inline images,
- use paragraph styles rather than excessive direct formatting,
- normalize run-level overrides,
- preserve section settings,
- preserve image aspect ratios,
- preserve editable text when possible.

Do not assume a file that opens in Word is mechanically clean.

---

# 26. Existing Document Restyle Mode

When restyling an existing GEMASTIK proposal:

1. Do not rewrite content unless explicitly asked.
2. Preserve section order.
3. Preserve citations.
4. Preserve figures and tables unless they must be resized/reflowed.
5. Normalize fonts.
6. Normalize paragraph indentation.
7. Normalize heading hierarchy.
8. Repair table pagination.
9. Repair figure-caption pagination.
10. Repair TOC/page-number mechanics.
11. Remove decorative Word styling.
12. Re-render and compare against the original to ensure no content disappeared.

If a content error is noticed during a style-only task, report it separately rather than silently rewriting it.

---

# 27. Manual Baseline Lessons

The desired house style is modeled on a manually prepared academic GEMASTIK proposal, with these retained characteristics:

- Times New Roman-like serif appearance,
- 12 pt body,
- approximately 1.5 line spacing,
- justified prose,
- black-and-white presentation,
- compact headings,
- ordinary academic tables,
- centered italic captions,
- large software screenshots,
- single-column report layout,
- no decorative corporate-report styling.

Do **not** preserve the baseline document's mechanical defects.

Specifically fix:

- font/theme inheritance,
- excessive nested paragraph left indents,
- table rows split awkwardly across pages,
- missing repeated table headers,
- orphaned figure captions,
- undersized screenshots,
- accidental blank/mostly blank pages,
- weak TOC page-number mechanics,
- cover image/text overlap,
- inconsistent pseudocode typography.

---

# 28. Render-and-Verify Workflow

Every DOCX creation or meaningful formatting edit must end with visual QA.

## Required workflow

1. Create or edit the DOCX.
2. Render the DOCX to page PNGs.
3. Inspect **every page** at 100% zoom.
4. Fix all visible defects.
5. Render again.
6. Repeat until clean.
7. Deliver only the final DOCX unless the user asks for QA files.

Use the canonical DOCX renderer available in the environment.

Visual review must check:

- font consistency,
- heading hierarchy,
- page breaks,
- table width,
- table row splits,
- repeated headers,
- figure resolution,
- figure-caption binding,
- screenshot readability,
- cover spacing,
- TOC alignment,
- page numbering,
- references,
- unexpected blank pages,
- clipping,
- overlap,
- missing glyphs.

A programmatically valid DOCX is not enough.

---

# 29. Mechanical Lint Before Delivery

Before delivery, verify:

- [ ] A4 page size
- [ ] portrait except intentional landscape sections
- [ ] correct margins
- [ ] Times New Roman enforced throughout
- [ ] no Calibri/Cambria/Aptos theme leakage
- [ ] body is 12 pt
- [ ] body is justified
- [ ] body line spacing is 1.5
- [ ] normal body left indent is 0 cm
- [ ] first-line indent is approximately 0.75 cm
- [ ] headings are black and compact
- [ ] no giant Word default headings
- [ ] no colored report UI
- [ ] no random bold phrases
- [ ] tables fit inside page width
- [ ] no ordinary word fragmentation caused by narrow columns
- [ ] table headers repeat across pages
- [ ] table rows do not split unnecessarily
- [ ] figures are readable
- [ ] figures preserve aspect ratio
- [ ] every figure has a descriptive caption
- [ ] no orphaned captions
- [ ] TOC has page numbers
- [ ] body begins cleanly after front matter
- [ ] page numbers are correct
- [ ] pseudocode is monospace and left aligned
- [ ] references use consistent hanging indent
- [ ] no cover overlap
- [ ] no accidental blank pages
- [ ] all pages visually inspected after final render

---

# 30. Anti-Patterns

Reject or repair documents that look like:

## AI corporate report

Symptoms:

- Aptos/Calibri,
- blue headings,
- enormous heading sizes,
- cards,
- KPI tiles,
- colored table headers,
- excessive white space,
- every idea converted into a table.

## Thesis clone

Symptoms:

- unnecessary 4 cm binding margin,
- huge chapter-start whitespace,
- overly ceremonial section pages,
- excessive nested indentation,
- page count wasted on formatting conventions not required by GEMASTIK.

## IEEE imitation

Symptoms:

- manually created two-column layout,
- 9–10 pt body copied from memory,
- conference-paper title block used for proposal,
- compressed screenshots.

For the final paper, use the real official template instead.

## Broken manual document

Symptoms:

- figure and caption on different pages,
- table header missing after page break,
- row text split into unreadable fragments,
- cover logo overlaps metadata,
- TOC without page numbers,
- inconsistent fonts caused by Word themes.

---

# 31. Default Decision Rules

When unsure:

- choose **Times New Roman 12**,
- choose **black**,
- choose **1.5 spacing**,
- choose **single column**,
- choose **prose instead of a table** unless comparison requires a table,
- choose **one large readable screenshot instead of several tiny ones**,
- choose **compact 12 pt headings instead of visually dramatic headings**,
- choose **plain borders instead of colored table styling**,
- choose **stable inline layout instead of floating objects**,
- choose **manual-looking academic restraint over generated-report polish**.

---

# 32. Final Standard

The final document should feel like:

> a technically strong student team manually prepared a disciplined university competition proposal in Microsoft Word.

It should not feel like:

> an LLM generated a "professional report" template and poured the content into it.

The formatting is successful when a judge notices the technical content, not the document styling.
