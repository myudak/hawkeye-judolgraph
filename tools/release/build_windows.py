"""Build the reproducible HAWK-EYE Windows onedir, portable ZIP, and installer."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "build" / "windows"
DIST_ROOT = ROOT / "dist"
WINDOWS_DIST = DIST_ROOT / "windows"
APP_DIST = WINDOWS_DIST / "HAWK-EYE"
SPEC = ROOT / "distribution" / "windows" / "hawkeye.spec"
ENGINE_INIT = ROOT / "apps" / "api" / "src" / "hawkeye" / "__init__.py"


def main() -> int:
    args = _parser().parse_args()
    if os.name != "nt":
        raise SystemExit("Windows bundles must be built on Windows")
    _require_matching_version(args.version)
    _require_frontend_bundle()
    _clean_known_output()

    environment = os.environ.copy()
    environment["PLAYWRIGHT_BROWSERS_PATH"] = "0"
    if args.tesseract_dir:
        environment["HAWKEYE_BUNDLE_TESSERACT"] = str(args.tesseract_dir.resolve())

    if not args.skip_browser_install:
        _run([sys.executable, "-m", "playwright", "install", "chromium"], env=environment)

    version_file = BUILD_ROOT / "version_info.txt"
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(_version_info(args.version), encoding="utf-8")
    environment["HAWKEYE_VERSION_FILE"] = str(version_file)

    _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(WINDOWS_DIST),
            "--workpath",
            str(BUILD_ROOT / "pyinstaller"),
            str(SPEC),
        ],
        env=environment,
    )
    _copy_distribution_docs()
    _verify_bundle()

    archive = _portable_archive(args.version)
    outputs = [archive]
    if args.installer:
        outputs.append(_build_installer(args.version, args.iscc))
    checksum_path = _write_checksums(outputs)

    print(f"Windows app: {APP_DIST}")
    for output in outputs:
        print(f"Release asset: {output}")
    print(f"Checksums: {checksum_path}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.0.1")
    parser.add_argument("--installer", action="store_true")
    parser.add_argument("--skip-browser-install", action="store_true")
    parser.add_argument("--iscc", type=Path, default=None)
    parser.add_argument("--tesseract-dir", type=Path, default=None)
    return parser


def _require_frontend_bundle() -> None:
    static = ROOT / "apps" / "api" / "src" / "hawkeye" / "review_app" / "static"
    required = (static / "index.html", static / "favicon.ico")
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Run `pnpm build` first; missing: " + ", ".join(missing))


def _clean_known_output() -> None:
    for path in (BUILD_ROOT, WINDOWS_DIST):
        resolved = path.resolve()
        if resolved not in {BUILD_ROOT.resolve(), WINDOWS_DIST.resolve()}:
            raise SystemExit(f"Refusing to clean unexpected path: {resolved}")
        try:
            shutil.rmtree(resolved)
        except FileNotFoundError:
            pass
        except OSError as error:
            raise SystemExit(
                f"Could not clean {resolved}. Close any running HAWK-EYE app and retry: {error}"
            ) from error
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    WINDOWS_DIST.mkdir(parents=True, exist_ok=True)


def _copy_distribution_docs() -> None:
    shutil.copy2(ROOT / "distribution" / "windows" / "README-WINDOWS.txt", APP_DIST)
    shutil.copy2(ROOT / "distribution" / "windows" / "settings.env.example", APP_DIST)


def _verify_bundle() -> None:
    required = (
        APP_DIST / "HAWK-EYE.exe",
        APP_DIST / "_internal" / "hawkeye" / "review_app" / "static" / "index.html",
        APP_DIST / "_internal" / "playwright" / "driver" / "package" / ".local-browsers",
        APP_DIST
        / "_internal"
        / "share"
        / "hawkeye"
        / "evaluation"
        / "controlled-interactions-v1.json",
        APP_DIST / "README-WINDOWS.txt",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Frozen bundle is incomplete: " + ", ".join(missing))
    forbidden = []
    for path in APP_DIST.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.casefold()
        if name in {".env", "settings.env"} or path.suffix.casefold() in {
            ".db",
            ".sqlite",
            ".sqlite3",
        }:
            forbidden.append(str(path.relative_to(APP_DIST)))
    if forbidden:
        raise SystemExit(
            "Frozen bundle contains local or secret-bearing files: " + ", ".join(forbidden)
        )


def _require_matching_version(version: str) -> None:
    source = ENGINE_INIT.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE)
    if match is None or match.group(1) != version:
        current = match.group(1) if match is not None else "unknown"
        raise SystemExit(f"Release version {version} does not match hawkeye.__version__ {current}")


def _portable_archive(version: str) -> Path:
    base = DIST_ROOT / f"HAWK-EYE-{version}-windows-x64-portable"
    archive = base.with_suffix(".zip")
    archive.unlink(missing_ok=True)
    created = Path(shutil.make_archive(str(base), "zip", WINDOWS_DIST, "HAWK-EYE"))
    return created


def _build_installer(version: str, configured_iscc: Path | None) -> Path:
    iscc = configured_iscc or _find_iscc()
    if iscc is None:
        raise SystemExit("Inno Setup 6 was not found; pass --iscc or omit --installer")
    _run(
        [
            str(iscc),
            f"/DMyAppVersion={version}",
            f"/DSourceDir={APP_DIST}",
            f"/DOutputDir={DIST_ROOT}",
            str(ROOT / "distribution" / "windows" / "installer.iss"),
        ]
    )
    output = DIST_ROOT / f"HAWK-EYE-Setup-{version}-windows-x64.exe"
    if not output.is_file():
        raise SystemExit(f"Installer was not generated: {output}")
    return output


def _find_iscc() -> Path | None:
    candidates = (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _write_checksums(outputs: list[Path]) -> Path:
    destination = DIST_ROOT / "SHA256SUMS-windows.txt"
    lines = []
    for output in outputs:
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        lines.append(f"{digest}  {output.name}")
    destination.write_text("\n".join(lines) + "\n", encoding="ascii")
    return destination


def _version_info(version: str) -> str:
    numeric = [int(value) for value in version.split(".") if value.isdigit()]
    numeric = (numeric + [0, 0, 0, 0])[:4]
    version_tuple = ", ".join(str(value) for value in numeric)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({version_tuple}), prodvers=({version_tuple}), mask=0x3f,
    flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'JudolGraph'),
    StringStruct('FileDescription', 'HAWK-EYE local investigation workspace'),
    StringStruct('FileVersion', '{version}'),
    StringStruct('InternalName', 'HAWK-EYE'),
    StringStruct('OriginalFilename', 'HAWK-EYE.exe'),
    StringStruct('ProductName', 'HAWK-EYE'),
    StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
"""


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
