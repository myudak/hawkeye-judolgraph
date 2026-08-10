"""Build a wheel only after the production web application is present."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = REPOSITORY_ROOT / "apps" / "api" / "src" / "hawkeye" / "review_app" / "static"


def main() -> int:
    required = ("index.html", "app.js", "styles.css")
    missing = [name for name in required if not (STATIC_ROOT / name).is_file()]
    chunks = list((STATIC_ROOT / "chunks").glob("*.js"))
    if missing or not chunks:
        detail = ", ".join(missing) if missing else "JavaScript chunks"
        raise SystemExit(f"Frontend production build is incomplete: missing {detail}")
    distribution_root = REPOSITORY_ROOT / "dist"
    if distribution_root.exists():
        shutil.rmtree(distribution_root)
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(distribution_root)],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
