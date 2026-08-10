# Research and Citations

## Repository evidence sources

The following are primary evidence for implementation claims and require no external factual
interpretation:

- `docs/GOAL.md`, `docs/DECISIONS.md`, and milestone design documents.
- `apps/api/src/hawkeye/` source code and Pydantic/SQLite schema.
- `apps/web/` React/TypeScript presentation source.
- `tests/` automated tests and controlled fixture manifest.
- `evaluation/benchmarks/g4-g9-controlled-results/raw-results.json`.
- Local ignored capability diagnostics generated explicitly by `hawkeye llm-probe`.
- Git commit history listed in the final completion report.

## Verified official competition sources

- **Title:** Penawaran GEMASTIK 2026
  - **Publisher:** Kementerian Pendidikan Tinggi, Sains, dan Teknologi
  - **Publication date:** 22 July 2026
  - **Access date:** 3 August 2026
  - **URL:** https://kemdiktisaintek.go.id/announcement/article/penawaran-gemastik-2026
  - **Supports:** the official GEMASTIK 2026 announcement and the organizer-linked guide.
  - **Caveat:** the announcement is not the detailed category rulebook.

- **Title:** Panduan GEMASTIK XIX Tahun 2026
  - **Publisher:** Balai Pengembangan Talenta Indonesia / Kemdiktisaintek
  - **Access date:** 3 August 2026
  - **URL:** https://drive.google.com/file/d/1ntd2hBOC9Way3bTC3LnCIX04I1_ylCim/view?usp=sharing
  - **Supports:** eligibility, 2026 schedule, Software Development preliminary/final deliverables,
    proposal section order, file/page limits, special rules, and judging weights.
  - **Caveat:** recheck the portal before submission because organizer rules and dates may be
    updated; the general and software-specific competition-history clauses require the stricter
    interpretation or organizer clarification.

The extracted requirements and project interpretation are consolidated in
`../docs/PRODUCT_AND_SUBMISSION_REQUIREMENTS.md`.

## UI/UX implementation reference

- **Title:** kitakitaaura/webgraph
  - **Author:** kitakitaaura
  - **Access date:** 3 August 2026
  - **URL:** https://github.com/kitakitaaura/webgraph
  - **Revision inspected:** `29449ee37746bf8e68f03c08659a2f58709079e3`
  - **Supports:** graph-first page composition, 2D canvas interaction, filters, inspector, minimap,
    responsive layout, timeline/replay controls, and the distinction between streamed live events
    and a generated demo graph.
  - **Caveat:** this is a design/implementation reference, not evidence for JudolGraph claims. Its
    README says MIT, but the inspected root has no standalone `LICENSE` file. No source is copied;
    verify licensing and attribution before any future reuse.

## External citations still required before final submission

No external urgency, impact, legal, or novelty statistic is currently asserted.
The final proposal should obtain and verify:

1. Authoritative Indonesian sources describing the relevant public-investigation problem and its
   measured scale, using neutral language that does not prejudge a domain or person.
2. Primary research or standards on digital evidence provenance, event sourcing/audit logs,
   accessibility/reduced motion, and safe browser automation where they materially support the
   proposal.
3. Official documentation for Playwright, FastAPI, SQLite, and other architectural components when
   describing supported behavior beyond what repository tests prove.
4. Official license metadata for exact dependency versions and Chromium distribution.

Every external citation must record title, publisher/author, publication date, access date, direct
URL, supported sentence, and any scope caveat. Do not cite search-result pages, promotional
summaries, unattributed statistics, or a source that merely resembles the desired claim.

## Citation worksheet

| Claim needing support | Required source type | Citation | Status |
|---|---|---|---|
| Official proposal order and page limit | Official GEMASTIK 2026 rules | Panduan GEMASTIK XIX Tahun 2026, linked above | verified 2026-08-03 |
| Problem urgency in Indonesia | Authoritative government/academic source | TODO — requires external source | planned |
| Provenance/audit importance | Primary standard or peer-reviewed research | TODO — requires external source | planned |
| Accessibility/reduced motion rationale | Authoritative accessibility standard | TODO — requires external source | planned |
| Technology behavior beyond local tests | Official project documentation | TODO — requires external source | planned |
| Dependency licenses | Official package metadata/repos | TODO — requires external source | planned |

The repository does not authorize legal conclusions about websites, operators, or users. Any legal
context must be reviewed by an authorized human and cited to current authoritative sources.
