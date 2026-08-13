# Windows Application and Release Guide

## End-user experience

The Windows distribution packages the existing FastAPI + React architecture; it does not rewrite
HAWK-EYE as Electron or grant the web interface additional privileges.

```text
HAWK-EYE.exe
    -> starts the bundled loopback FastAPI service
    -> verifies /health
    -> opens the default browser
    -> remains controllable from the notification area
```

The application binds only `127.0.0.1`. The tray menu can reopen the interface, open the data
folder, or stop the service. Starting a second copy reopens the healthy first instance instead of
starting another writer.

## Install and portable modes

The release workflow produces two equivalent application formats:

- `HAWK-EYE-Setup-<version>-windows-x64.exe` installs per user under
  `%LOCALAPPDATA%\Programs\HAWK-EYE`; it does not request administrator privileges.
- `HAWK-EYE-<version>-windows-x64-portable.zip` runs after the complete `HAWK-EYE` folder is
  extracted. Do not move only the `.exe`; its `_internal` directory contains the Python runtime,
  frontend, Chromium, and libraries.

Both formats store mutable state under `%LOCALAPPDATA%\HAWK-EYE`:

```text
HAWK-EYE/
├── Data/
│   ├── cases/
│   ├── comparisons/
│   └── workspace/
├── Logs/
│   └── hawkeye.log
└── settings.env       optional, user-created
```

Back up `Data` to preserve case artifacts, append-only SQLite review history, and comparisons.
Uninstalling the application intentionally leaves this user-owned state in place.

## Optional model configuration

The desktop app works through deterministic fallback without any credential. To enable an
OpenAI-compatible provider, copy `settings.env.example` from the portable folder to
`%LOCALAPPDATA%\HAWK-EYE\settings.env` and set the `HAWKEYE_LLM_*` values. Only keys beginning with
`HAWKEYE_` are accepted from this file, and process-level environment values take precedence.

Example for OpenRouter:

```dotenv
HAWKEYE_LLM_BASE_URL=https://openrouter.ai/api/v1
HAWKEYE_LLM_API_KEY=replace-me
HAWKEYE_LLM_MODEL=openai/gpt-5.6-luna
HAWKEYE_LLM_API_STYLE=chat_completions
HAWKEYE_LLM_TIMEOUT_SECONDS=30
```

Never place a real key in the application folder, Git repository, release archive, or issue log.

## Local reproducible build

Requirements: Windows x64, Python 3.12, uv, Node.js 22.12+, pnpm 11.3+, and optionally Inno Setup 6.

```powershell
pnpm install --frozen-lockfile
uv sync --locked --extra dev --extra desktop
pnpm build
uv run python tools/release/build_windows.py --version 1.0.0
uv run python tools/release/verify_windows_bundle.py dist/windows/HAWK-EYE/HAWK-EYE.exe
```

Add `--installer` when Inno Setup 6 is installed. The build script installs the Chromium revision
required by the locked Playwright version into the package and fails if the frontend or browser is
missing. Output is written only below `build/windows` and `dist`.

Tesseract is deliberately optional. A controlled builder may pass
`--tesseract-dir C:\path\to\pinned\tesseract` to include a reviewed portable runtime. Otherwise OCR
reports `unavailable` unless the operator configures `HAWKEYE_TESSERACT_PATH`; capture and
deterministic extraction continue normally.

## Automated CI and releases

`.github/workflows/ci.yml` runs locked frontend/backend quality gates on every main-branch push and
pull request. `.github/workflows/windows-release.yml` builds on a native Windows runner, executes the
frozen multiprocessing and Chromium self-test, starts the packaged server on an ephemeral loopback
port, verifies health and the React shell, creates SHA-256 checksums, and attests the release assets.

To publish a release:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

The tag workflow creates the portable ZIP and installer and attaches both to the matching GitHub
Release. A manual workflow dispatch builds downloadable workflow artifacts without creating a Git
tag or GitHub Release.

The output is currently unsigned. Windows may display a SmartScreen reputation warning until the
project owner obtains a code-signing certificate and adds an explicitly reviewed signing stage.
Do not describe checksums or GitHub provenance attestations as a replacement for code signing.

## Packaging boundaries

- PyInstaller uses `onedir`, avoiding a large Chromium extraction on every launch.
- `multiprocessing.freeze_support()` runs before application imports so the isolated capture worker
  is safe under Windows `spawn`.
- Browser binaries match the locked Playwright package and are never downloaded on first launch.
- The generated frontend remains a build input, not Git source.
- No `.env`, API key, captured case, SQLite workspace, or local report enters a release asset.
- The desktop package remains single-investigator and localhost-only; it is not a public deployment
  or multi-user authorization milestone.
