"""Small, explicit local filesystem storage for case artifacts and JSON outputs."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hawkeye.models import EvidenceRecord

_CASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_PAGE_ID_RE = re.compile(r"^page-[0-9]{3}$")


def make_case_id() -> str:
    """Create a filesystem-safe unique case identifier."""

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"case-{timestamp}-{uuid.uuid4().hex[:8]}"


@dataclass
class CaseStorage:
    """Owns one newly-created case directory and all of its relative artifact paths."""

    root: Path

    @classmethod
    def create(cls, output_root: Path, case_id: str) -> CaseStorage:
        if not _CASE_ID_RE.fullmatch(case_id):
            raise ValueError("case_id must use letters, digits, hyphens, or underscores only")
        root = output_root.expanduser().resolve() / case_id
        if root.exists():
            raise FileExistsError(f"Case output already exists: {root}")
        (root / "pages").mkdir(parents=True)
        (root / "screenshots").mkdir(parents=True)
        return cls(root=root)

    def write_json(self, relative_path: str, payload: Any) -> Path:
        destination = self._destination(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
        destination.write_text(f"{serialized}\n", encoding="utf-8")
        return destination

    def write_text(self, relative_path: str, content: str) -> Path:
        destination = self._destination(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        return destination

    def write_bytes(self, relative_path: str, content: bytes) -> Path:
        destination = self._destination(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return destination

    def log(self, message: str) -> None:
        timestamp = datetime.now(UTC).isoformat()
        with self._destination("run.log").open("a", encoding="utf-8") as output:
            output.write(f"{timestamp} {message}\n")

    def save_html(
        self,
        content: str,
        *,
        source_url: str,
        collected_at: datetime,
        page_id: str = "page-001",
        evidence_id: str | None = None,
    ) -> EvidenceRecord:
        self._validate_page_id(page_id)
        relative_path = f"pages/{page_id}.html"
        destination = self.write_text(relative_path, content)
        return EvidenceRecord(
            id=evidence_id or f"evidence-{page_id}",
            type="html_page",
            source_url=source_url,
            path=self.relative_path(destination),
            collected_at=collected_at,
            sha256=self.sha256_file(destination),
            page_id=page_id,
        )

    def save_screenshot(
        self,
        content: bytes,
        *,
        source_url: str,
        collected_at: datetime,
        viewport: dict[str, int],
        image_dimensions: dict[str, int],
        page_id: str = "page-001",
        evidence_id: str | None = None,
    ) -> EvidenceRecord:
        self._validate_page_id(page_id)
        relative_path = f"screenshots/{page_id}.png"
        destination = self.write_bytes(relative_path, content)
        suffix = page_id.removeprefix("page-")
        return EvidenceRecord(
            id=evidence_id or f"evidence-screenshot-{suffix}",
            type="screenshot",
            source_url=source_url,
            path=self.relative_path(destination),
            collected_at=collected_at,
            sha256=self.sha256_file(destination),
            page_id=page_id,
            viewport=viewport,
            image_dimensions=image_dimensions,
        )

    def save_network_event(
        self,
        payload: Any,
        *,
        source_url: str,
        collected_at: datetime,
        page_id: str,
        evidence_id: str | None = None,
    ) -> EvidenceRecord:
        """Persist a compact observed network event when no HTML artifact exists."""

        self._validate_page_id(page_id)
        relative_path = f"network/{page_id}-redirects.json"
        destination = self.write_json(relative_path, payload)
        return EvidenceRecord(
            id=evidence_id or f"evidence-network-{page_id.removeprefix('page-')}",
            type="network_event",
            source_url=source_url,
            path=self.relative_path(destination),
            collected_at=collected_at,
            sha256=self.sha256_file(destination),
            page_id=page_id,
        )

    def relative_path(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    @staticmethod
    def sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _destination(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Artifact path must remain inside its case directory")
        return candidate

    @staticmethod
    def _validate_page_id(page_id: str) -> None:
        if not _PAGE_ID_RE.fullmatch(page_id):
            raise ValueError("page_id must use the form page-001")
