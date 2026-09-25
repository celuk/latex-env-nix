import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def convert_with_pdftoppm(input_pdf: Path, output_png: Path, dpi: int) -> None:
    """Convert a single PDF file to PNG using poppler's pdftoppm."""
    output_base = output_png.with_suffix("")
    cmd = [
        "pdftoppm",
        "-png",
        "-r",
        str(dpi),
        "-singlefile",
        str(input_pdf),
        str(output_base),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "pdftoppm conversion failed")


def convert_with_sips(input_pdf: Path, output_png: Path, dpi: int) -> None:
    """Fallback converter using macOS sips with explicit DPI."""
    cmd = [
        "sips",
        "-s",
        "dpiWidth",
        str(dpi),
        "-s",
        "dpiHeight",
        str(dpi),
        "-s",
        "format",
        "png",
        str(input_pdf),
        "--out",
        str(output_png),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "sips conversion failed")


def convert_pdf_to_png(input_pdf: Path, output_png: Path, dpi: int) -> None:
    """Convert a single PDF file to PNG with high quality."""
    if shutil.which("pdftoppm") is not None:
        convert_with_pdftoppm(input_pdf, output_png, dpi)
        return

    if shutil.which("sips") is not None:
        convert_with_sips(input_pdf, output_png, dpi)
        return

    raise RuntimeError("No supported converter found. Install pdftoppm or use macOS sips.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert one PDF file to PNG."
    )
    parser.add_argument(
        "-i",
        "--input-pdf",
        required=True,
        help="Input PDF file path",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="figures-png",
        help="Directory where PNG file will be written (default: figures-png)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=600,
        help="Rasterization DPI for PNG output (default: 600)",
    )
    args = parser.parse_args()

    if args.dpi <= 0:
        print("Error: --dpi must be a positive integer.")
        return 1

    input_pdf = Path(args.input_pdf)
    output_dir = Path(args.output_dir)

    if not input_pdf.exists() or not input_pdf.is_file():
        print(f"Error: input PDF not found: {input_pdf}")
        return 1

    if input_pdf.suffix.lower() != ".pdf":
        print(f"Error: input file is not a PDF: {input_pdf}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    output_png = output_dir / f"{input_pdf.stem}.png"

    try:
        convert_pdf_to_png(input_pdf, output_png, args.dpi)
        print(f"[+] {input_pdf} -> {output_png} (dpi={args.dpi})")
        return 0
    except Exception as exc:
        print(f"[-] Failed: {input_pdf} ({exc})")
        return 1


if __name__ == "__main__":
    sys.exit(main())