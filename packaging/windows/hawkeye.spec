# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

import playwright
from PyInstaller.utils.hooks import collect_all, collect_submodules


REPOSITORY_ROOT = Path(SPECPATH).resolve().parents[1]
STATIC_ROOT = REPOSITORY_ROOT / "apps" / "api" / "src" / "hawkeye" / "review_app" / "static"
PLAYWRIGHT_ROOT = Path(playwright.__file__).resolve().parent
PLAYWRIGHT_BROWSERS = PLAYWRIGHT_ROOT / "driver" / "package" / ".local-browsers"

required_static = [
    STATIC_ROOT / "index.html",
    STATIC_ROOT / "favicon.ico",
]
missing_static = [str(path) for path in required_static if not path.is_file()]
if missing_static:
    raise SystemExit(f"Frontend bundle is incomplete: {', '.join(missing_static)}")
if not PLAYWRIGHT_BROWSERS.is_dir():
    raise SystemExit(
        "Bundled Chromium is missing. Run with PLAYWRIGHT_BROWSERS_PATH=0 and install chromium."
    )

playwright_datas, playwright_binaries, playwright_hidden = collect_all("playwright")
tldextract_datas, tldextract_binaries, tldextract_hidden = collect_all("tldextract")
datas = [
    (str(STATIC_ROOT), "hawkeye/review_app/static"),
    (
        str(REPOSITORY_ROOT / "evaluation" / "fixtures" / "controlled-interactions-v1.json"),
        "share/hawkeye/evaluation",
    ),
    (
        str(REPOSITORY_ROOT / "apps" / "web" / "src" / "assets" / "hawkeye-avatar.png"),
        "desktop-assets",
    ),
    (
        str(REPOSITORY_ROOT / "apps" / "web" / "src" / "assets" / "hawkeye-banner.png"),
        "desktop-assets",
    ),
    (str(PLAYWRIGHT_BROWSERS), "playwright/driver/package/.local-browsers"),
    *playwright_datas,
    *tldextract_datas,
]

tesseract_root = os.environ.get("HAWKEYE_BUNDLE_TESSERACT", "").strip()
if tesseract_root:
    tesseract_path = Path(tesseract_root).resolve()
    if not (tesseract_path / "tesseract.exe").is_file():
        raise SystemExit("HAWKEYE_BUNDLE_TESSERACT must contain tesseract.exe")
    datas.append((str(tesseract_path), "tesseract"))

hiddenimports = sorted(
    set(
        playwright_hidden
        + tldextract_hidden
        + collect_submodules("pystray")
        + collect_submodules("uvicorn")
        + ["PIL._tkinter_finder"]
    )
)

a = Analysis(
    [str(REPOSITORY_ROOT / "packaging" / "windows" / "launcher.py")],
    pathex=[str(REPOSITORY_ROOT / "apps" / "api" / "src")],
    binaries=playwright_binaries + tldextract_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff", "mypy"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HAWK-EYE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    icon=str(REPOSITORY_ROOT / "apps" / "web" / "src" / "assets" / "favicon.ico"),
    version=os.environ["HAWKEYE_VERSION_FILE"],
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HAWK-EYE",
)
