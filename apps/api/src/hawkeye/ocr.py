"""Optional bounded local OCR for screenshot-only public observables."""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field

MAX_OCR_INPUT_BYTES = 10_000_000
MAX_OCR_PIXELS = 16_000_000
MAX_OCR_DIMENSION = 2_400
MAX_OCR_OUTPUT_BYTES = 2_000_000


class OcrRegion(BaseModel):
    text: str = Field(max_length=1000)
    confidence: float = Field(ge=0.0, le=1.0)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class BoundedOcrResult(BaseModel):
    status: Literal["completed", "unavailable", "skipped", "failed"]
    engine: Literal["tesseract_local"] = "tesseract_local"
    reason: str
    text: str = Field(default="", max_length=100_000)
    regions: list[OcrRegion] = Field(default_factory=list, max_length=500)
    source_width: int = Field(default=0, ge=0)
    source_height: int = Field(default=0, ge=0)
    processed_width: int = Field(default=0, ge=0)
    processed_height: int = Field(default=0, ge=0)


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def run_bounded_ocr(
    image_bytes: bytes,
    *,
    executable: str | None = None,
    runner: Runner = subprocess.run,
) -> BoundedOcrResult:
    """Run one known local OCR binary with strict byte, pixel, output, and time limits."""

    if len(image_bytes) > MAX_OCR_INPUT_BYTES:
        return BoundedOcrResult(status="skipped", reason="ocr_input_exceeds_10_mb")
    resolved = _resolve_tesseract(executable)
    if resolved is None:
        return BoundedOcrResult(status="unavailable", reason="tesseract_not_available")
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except (OSError, ValueError):
        return BoundedOcrResult(status="failed", reason="ocr_image_decode_failed")
    source_width, source_height = image.size
    if source_width <= 0 or source_height <= 0:
        return BoundedOcrResult(status="failed", reason="ocr_image_has_no_pixels")
    if source_width * source_height > MAX_OCR_PIXELS:
        image.thumbnail((MAX_OCR_DIMENSION, MAX_OCR_DIMENSION))
    processed_width, processed_height = image.size
    encoded = io.BytesIO()
    image.convert("RGB").save(encoded, format="PNG", optimize=True)
    try:
        completed = runner(
            [resolved, "stdin", "stdout", "--psm", "11", "tsv"],
            input=encoded.getvalue(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=12,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return BoundedOcrResult(status="failed", reason="tesseract_execution_failed")
    if completed.returncode != 0:
        return BoundedOcrResult(status="failed", reason="tesseract_nonzero_exit")
    if len(completed.stdout) > MAX_OCR_OUTPUT_BYTES:
        return BoundedOcrResult(status="failed", reason="tesseract_output_exceeds_2_mb")
    try:
        output = completed.stdout.decode("utf-8", errors="replace")
        regions = parse_tesseract_tsv(
            output,
            source_width=source_width,
            source_height=source_height,
            processed_width=processed_width,
            processed_height=processed_height,
        )
    except (ValueError, csv.Error):
        return BoundedOcrResult(status="failed", reason="tesseract_tsv_invalid")
    text = "\n".join(item.text for item in regions)
    return BoundedOcrResult(
        status="completed",
        reason="bounded_local_ocr_completed",
        text=text[:100_000],
        regions=regions,
        source_width=source_width,
        source_height=source_height,
        processed_width=processed_width,
        processed_height=processed_height,
    )


def parse_tesseract_tsv(
    payload: str,
    *,
    source_width: int,
    source_height: int,
    processed_width: int,
    processed_height: int,
) -> list[OcrRegion]:
    """Group accepted OCR words into bounded line regions and restore source coordinates."""

    if min(source_width, source_height, processed_width, processed_height) <= 0:
        raise ValueError("OCR dimensions must be positive")
    reader = csv.DictReader(io.StringIO(payload), delimiter="\t")
    required = {
        "block_num",
        "par_num",
        "line_num",
        "left",
        "top",
        "width",
        "height",
        "conf",
        "text",
    }
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError("Tesseract TSV columns are incomplete")
    grouped: dict[tuple[int, int, int], list[tuple[str, float, int, int, int, int]]] = {}
    for row in reader:
        text = str(row.get("text", "")).strip()
        if not text:
            continue
        try:
            confidence = float(row["conf"])
            left = int(row["left"])
            top = int(row["top"])
            width = int(row["width"])
            height = int(row["height"])
            key = (int(row["block_num"]), int(row["par_num"]), int(row["line_num"]))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Tesseract TSV row is invalid") from error
        if confidence < 20 or width <= 0 or height <= 0:
            continue
        grouped.setdefault(key, []).append((text, confidence, left, top, width, height))
    scale_x = source_width / processed_width
    scale_y = source_height / processed_height
    regions: list[OcrRegion] = []
    for words in list(grouped.values())[:500]:
        left = min(item[2] for item in words)
        top = min(item[3] for item in words)
        right = max(item[2] + item[4] for item in words)
        bottom = max(item[3] + item[5] for item in words)
        regions.append(
            OcrRegion(
                text=" ".join(item[0] for item in words)[:1000],
                confidence=min(0.99, sum(item[1] for item in words) / len(words) / 100),
                x=max(0, round(left * scale_x)),
                y=max(0, round(top * scale_y)),
                width=max(1, round((right - left) * scale_x)),
                height=max(1, round((bottom - top) * scale_y)),
            )
        )
    return regions


def _resolve_tesseract(executable: str | None) -> str | None:
    requested = executable or os.environ.get("HAWKEYE_TESSERACT_PATH")
    if requested:
        path = Path(requested).expanduser()
        if path.is_absolute() and path.is_file():
            return str(path.resolve())
        return shutil.which(requested)
    return shutil.which("tesseract")
