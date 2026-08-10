"""Location helpers that work in the source monorepo and installed wheel."""

from __future__ import annotations

import sysconfig
from pathlib import Path


def repository_root(start: Path | None = None) -> Path | None:
    current = (start or Path(__file__)).resolve()
    for parent in (current, *current.parents):
        if (parent / "pyproject.toml").is_file() and (parent / "apps").is_dir():
            return parent
    return None


def controlled_fixture_path() -> Path:
    root = repository_root()
    if root is not None:
        source_fixture = root / "evaluation" / "fixtures" / "controlled-interactions-v1.json"
        if source_fixture.is_file():
            return source_fixture
    relative = Path("share/hawkeye/evaluation/controlled-interactions-v1.json")
    package_file = Path(__file__).resolve()
    installation_roots = (Path(sysconfig.get_path("data")), *package_file.parents)
    for installation_root in dict.fromkeys(installation_roots):
        installed = installation_root / relative
        if installed.is_file():
            return installed
    raise FileNotFoundError("The controlled interaction fixture is not installed")
