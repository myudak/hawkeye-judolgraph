"""Rasterize PDF QA copies to one PNG per page with pypdfium2."""

from __future__ import annotations

import argparse
from pathlib import Path

import pypdfium2 as pdfium


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--scale", type=float, default=1.6)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for pdf_path in sorted(args.input_dir.glob("*.pdf")):
        destination = args.output_dir / pdf_path.stem
        destination.mkdir(parents=True, exist_ok=True)
        pdf = pdfium.PdfDocument(pdf_path)
        try:
            for index in range(len(pdf)):
                page = pdf[index]
                try:
                    bitmap = page.render(scale=args.scale)
                    image = bitmap.to_pil()
                    image.save(destination / f"page-{index + 1:02d}.png")
                finally:
                    page.close()
        finally:
            pdf.close()
        print(f"Rasterized {pdf_path.name}: {len(list(destination.glob('page-*.png')))} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
