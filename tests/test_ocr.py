from __future__ import annotations

import subprocess
from io import BytesIO

from PIL import Image

from hawkeye.ocr import parse_tesseract_tsv, run_bounded_ocr

TSV_HEADER = "\t".join(
    [
        "level",
        "page_num",
        "block_num",
        "par_num",
        "line_num",
        "word_num",
        "left",
        "top",
        "width",
        "height",
        "conf",
        "text",
    ]
)
TSV = f"""{TSV_HEADER}
5\t1\t1\t1\t1\t1\t10\t20\t30\t10\t91\tWhatsApp
5\t1\t1\t1\t1\t2\t45\t20\t50\t10\t87\t+63912345
"""


def test_parse_tesseract_tsv_groups_lines_and_restores_source_coordinates() -> None:
    regions = parse_tesseract_tsv(
        TSV,
        source_width=200,
        source_height=100,
        processed_width=100,
        processed_height=50,
    )

    assert len(regions) == 1
    assert regions[0].text == "WhatsApp +63912345"
    assert (regions[0].x, regions[0].y, regions[0].width, regions[0].height) == (
        20,
        40,
        170,
        20,
    )


def test_bounded_ocr_reports_unavailable_dependency() -> None:
    image = Image.new("RGB", (20, 20), "white")
    payload = BytesIO()
    image.save(payload, format="PNG")

    result = run_bounded_ocr(payload.getvalue(), executable="definitely-not-tesseract")

    assert result.status == "unavailable"
    assert result.reason == "tesseract_not_available"


def test_bounded_ocr_uses_fixed_command_and_returns_provenance() -> None:
    image = Image.new("RGB", (100, 50), "white")
    payload = BytesIO()
    image.save(payload, format="PNG")
    calls: list[list[str]] = []

    def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=TSV.encode(), stderr=b"")

    result = run_bounded_ocr(payload.getvalue(), executable=__file__, runner=runner)

    assert result.status == "completed"
    assert result.text == "WhatsApp +63912345"
    assert calls == [[__file__, "stdin", "stdout", "--psm", "11", "tsv"]]
