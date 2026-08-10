# HAWK-EYE / JudolGraph

HAWK-EYE is a local, evidence-first OSINT instrument for investigating public web pages and
reviewing possible relationships in online-gambling ecosystems. It captures a bounded public
site, preserves hash-backed artifacts, extracts deterministic observations, projects an
event-sourced graph, and keeps candidate relationships pending until human review.

It does **not** log in, submit forms, purchase, message, solve access challenges, bypass controls,
or automatically crawl generated candidates. A candidate or similarity score is not proof of
ownership, identity, criminality, or legal status.

## Repository map

```text
apps/
├── api/
│   └── src/hawkeye/       FastAPI, collector, agent adapter, storage, CLI
└── web/                   React 19, Vite, Tailwind, shadcn/ui
tests/                     Stable controlled test and evaluation node IDs
evaluation/                Fixtures, manifests, benchmarks, ignored live output
docs/                      Durable architecture, policy, and evaluator context
gemastik-2026/             Competition Markdown package
infra/docker/              Container-specific support files
data/                      Ignored local cases/workspace/comparisons
```

Python dependencies and packaging are managed by `uv` from the root `pyproject.toml` and
`uv.lock`. JavaScript dependencies and developer orchestration are managed by `pnpm` from the
single root `pnpm-lock.yaml`.

## Quick start with Docker

Requirements: Docker Desktop or Docker Engine with Compose v2.

```powershell
docker compose up --build
```

Open `http://127.0.0.1:8760`. Compose publishes the application on host loopback only and mounts
`./data` at `/data`; cases and append-only review history survive restarts.

Stop the service without deleting local data:

```powershell
docker compose down
```

The image builds the React bundle, builds and installs the Python wheel, and runs Chromium plus
Tesseract as the non-root `pwuser`. Docker's default seccomp policy remains active; Compose drops
all capabilities, enables `no-new-privileges`, uses an init process, and provides shared IPC for
Chromium. This is a local single-investigator boundary, not a public deployment configuration.

## Manual setup with pnpm + uv

Requirements: Python 3.12, `uv`, Node.js 22+, and pnpm 11.3.0 (Corepack may provide pnpm).

```powershell
pnpm install --frozen-lockfile
pnpm setup
pnpm dev
```

`pnpm setup` runs a locked Python sync and installs the pinned Playwright Chromium runtime. During
development, Vite listens on loopback and proxies `/api` and `/health` to FastAPI with HMR.

Production-like local mode builds the generated UI bundle and serves it from FastAPI:

```powershell
pnpm start
```

Useful root commands:

| Command | Purpose |
| --- | --- |
| `pnpm dev` | FastAPI + Vite development servers |
| `pnpm build` | Generate the React bundle inside the backend package tree |
| `pnpm start` | Build and run the loopback-only local application |
| `pnpm check` | Frontend and Python format, lint, type, test, build, and diff gates |
| `pnpm package` | Build UI and a wheel containing the complete UI bundle |
| `pnpm clean` | Remove generated static/build/dist output; never removes `data` |

## Data-directory contract

`hawkeye app` and the container use one explicit root:

```text
data/
├── cases/                 Canonical case packages and artifacts
├── workspace/             SQLite events, assertions, reviews, run artifacts
└── comparisons/           Verified offline comparison documents
```

Everything under `data/` is local and ignored by Git. Generated UI static files, `.venv`,
`node_modules`, `build`, `dist`, live captures, reports, temporary files, and DOCX/PDF exports are
also ignored. Source code, controlled fixtures, tests, docs, and GEMASTIK Markdown remain tracked.

Back up a local installation by stopping HAWK-EYE and copying the entire `data/` directory. For a
single investigation, use the Summary page's JSON, Markdown, or case-archive export; exports do not
replace the canonical case or SQLite history.

## Optional OpenAI-compatible model

The model is optional. With no configuration, HAWK-EYE uses its deterministic safe fallback and
the complete product remains usable.

```dotenv
HAWKEYE_LLM_BASE_URL=https://provider.example/v1
HAWKEYE_LLM_API_KEY=replace-locally
HAWKEYE_LLM_MODEL=model-id
HAWKEYE_LLM_API_STYLE=auto
HAWKEYE_LLM_TIMEOUT_SECONDS=15
```

`CODEX_BASE_URL`, `CODEX_API_KEY`, and `CODEX_MODEL` are accepted as local aliases for a
Codex-compatible OpenAI gateway. Secrets belong only in process environment or an ignored `.env`;
never put them in source, Compose images, command-line arguments, case packages, events, exports,
or diagnostics.

`HAWKEYE_LLM_BASE_URL` must use HTTPS except for loopback development and must not contain URL
credentials, a query, or a fragment. Redirects are rejected. `auto` tries the Responses API first
and uses Chat Completions only when the Responses route returns `404` or `405`; schema and general
HTTP errors do not trigger route switching. All output must validate as `AgentDecision`, and the
model receives only normalized context plus server-issued safe references.

Landing-page requests never probe or spend model tokens. To perform an explicit strict-schema
handshake:

```powershell
uv run hawkeye llm-probe --output verification-output/llm-capability.json
```

## Local application and CLI

Run the complete application manually:

```powershell
uv run hawkeye app --data ./data --port 8760
```

The normal CLI has no arbitrary `--host` option and binds to `127.0.0.1`. The separate internal
container entry point binds inside the container; Compose still publishes only on host loopback.

Collect one bounded public seed directly:

```powershell
uv run hawkeye investigate https://example.com --output ./data/cases
```

Important hard limits include same-site BFS depth 0–1, at most five HTML pages, one browser page at
a time, five redirects per page, per-page and whole-case timeouts, request/declared-byte budgets,
and bounded canonical HTML/screenshot persistence. Unsafe schemes, private/loopback/link-local
destinations, metadata services, unsafe redirects, popups, downloads, WebSockets, and service
workers are blocked by default. Loopback collection exists only behind the explicit test policy.

Other core commands:

```powershell
uv run hawkeye compare <case-a> <case-b> --output <comparison.json>
uv run hawkeye evaluate <manifest.json> <case-directory> --report <report.json>
uv run hawkeye diagnose <case-directory> --mode live
uv run hawkeye benchmark --output <new-directory> --agent-attempts 3
uv run hawkeye demo --output <new-directory>
```

The authoritative ten-scenario benchmark remains deterministic fixture truth. Live URLs are
opt-in qualitative observations only and are never automated test truth.

## Case and evidence semantics

A canonical case can contain:

```text
case.json
pages.json
frontier.json
evidence.json
entities.json
observations.json
candidates.json
candidate_observations.json
graph.json
run.log
pages/*.html
pages/*-visible.txt
screenshots/*.png
capture/*-response.json
capture/*-readiness.json
network/*-redirects.json
```

The loader verifies completion state, schema, IDs/references, containment, reparse points,
artifact sizes, SHA-256 values, UTF-8 text, JSON event bodies, and bounded PNG dimensions before
display. Captured HTML is served only as a text attachment. Screenshots and semantic observations
remain linked to their source page/artifact. Graph animation and replay are projections of
persisted truth, never new evidence.

Candidate generation remains relationship-neutral and pending. External discovery is isolated and
opt-in; returned destinations are not fed back into the browser. Recollection of a directly
observed candidate requires explicit approval and still creates only a reviewable assertion.
SQLite events, assertions, and review decisions are append-only; the current state is reduced from
history.

## Clean build and verification

For an offline repeat when dependencies are already cached:

```powershell
pnpm clean
pnpm install --frozen-lockfile --offline
uv sync --locked --offline --extra dev
pnpm build
pnpm check
pnpm package
```

Inspect the produced wheel under `dist/`; it must contain `hawkeye/review_app/static/index.html`,
`app.js`, `styles.css`, hashed chunks, fonts/images, CLI entry points, and the controlled interaction
fixture. Packaging fails when the UI bundle is incomplete.

## Troubleshooting

- **Chromium download is slow:** rerun `uv run playwright install chromium` when connectivity is
  stable. Do not use live URLs as a substitute for controlled tests.
- **Executable does not exist:** confirm `playwright==1.50.0` from `uv.lock`, then reinstall that
  version's Chromium. The Docker image uses the matching `v1.50.0-noble` browser image.
- **Linux container cannot write `data`:** ensure the host `./data` directory is writable by the
  container's non-root user before `docker compose up`.
- **Container cannot reach a host-local model gateway:** use
  `http://host.docker.internal:<port>/v1` only for local development; non-loopback plaintext URLs
  are rejected by model configuration.
- **Port already used:** set `HAWKEYE_PORT` in an ignored `.env`, for example `8770`. Compose still
  binds `127.0.0.1` only.
- **Docker daemon unavailable:** start Docker Desktop/Engine; `docker compose config` can validate
  syntax but cannot prove the image or browser runtime without the daemon.

## Project context

The durable goal, roadmap, decisions, current status, evaluation protocol, frontend truth boundary,
and threat model live under `docs/`. Historical G2/G3 tags, benchmark results, evidence packages,
and review history are not rewritten by this repository reorganization. The owner-authenticated
G4–G9 live observations from 2026-08-03 remain historical qualitative validation, not a current
Codex-LB dependency or a claim of live-site accuracy.
