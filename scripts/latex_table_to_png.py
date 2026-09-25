"""
Extract LaTeX tables from a .tex file and render each as a standalone PNG image.

Usage:
    python3 scripts/latex_table_to_png.py -t presentation.tex -o figures/tables/
    python3 scripts/latex_table_to_png.py -t presentation.tex -o figures/tables/ --dpi 300
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path


_TURKISH_ASCII_MAP = {
    "\u00c7": "C",
    "\u00e7": "c",
    "\u011e": "G",
    "\u011f": "g",
    "\u0130": "I",
    "\u0131": "i",
    "\u00d6": "O",
    "\u00f6": "o",
    "\u015e": "S",
    "\u015f": "s",
    "\u00dc": "U",
    "\u00fc": "u",
}


def _slugify(text, max_len=60, fallback="table"):
    mapped = "".join(_TURKISH_ASCII_MAP.get(ch, ch) for ch in text)
    normalized = unicodedata.normalize("NFKD", mapped)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text).strip("_").lower()
    if not slug:
        slug = fallback
    return slug[:max_len]


def extract_tables(tex_path):
    """Extract all table environments from a .tex file.

    Returns a list of dicts with keys: 'content', 'caption', 'index'.
    The 'content' is the tabular environment only (no \\caption, no \\begin{table}).
    """
    with open(tex_path, "r") as f:
        text = f.read()

    # Match \begin{table}[...] ... \end{table} blocks (float spec is optional)
    table_pattern = re.compile(
        r"\\begin\{table\}(?:\[[^\]]*\])?\s*(.*?)\\end\{table\}", re.DOTALL
    )

    tables = []
    for i, match in enumerate(table_pattern.finditer(text)):
        body = match.group(1)

        # Extract caption text if present (handles both \caption{} and \caption*{})
        cap_match = re.search(r"\\caption\*?\{(.+?)\}", body)
        caption = cap_match.group(1) if cap_match else f"table_{i+1}"

        # Derive a filesystem-safe slug from the caption
        slug = _slugify(caption, fallback=f"table_{i+1}")

        # Remove \caption{...} / \caption*{...} and \centering / \footnotesize from the body
        # so we render only the tabular content
        clean = re.sub(r"\\caption\*?\{.+?\}", "", body)

        tables.append({"content": clean.strip(), "caption": caption, "slug": slug, "index": i + 1})

    return tables


def render_table_to_png(table_latex, output_png, dpi=300, textwidth="14.5cm"):
    """Compile a standalone LaTeX document with the table and convert to PNG."""

    standalone_template = r"""\documentclass[border=8pt,VARWIDTH_OPTION]{standalone}
\usepackage[T1]{fontenc}
\usepackage{booktabs}
\usepackage{xcolor}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{array}
\usepackage{tabularx}
\usepackage{pifont}

% Match beamer-like sans-serif look
\renewcommand{\familydefault}{\sfdefault}

% NVIDIA-inspired color accents (optional)
\definecolor{nvgreen}{RGB}{118,185,0}
\definecolor{darkbg}{RGB}{30,30,40}

\begin{document}
TABLE_CONTENT_PLACEHOLDER
\end{document}
"""

    uses_tabularx = r"\begin{tabularx}" in table_latex

    if uses_tabularx:
        # For tabularx tables: don't use varwidth (it overrides \linewidth).
        # Instead, wrap the table in a minipage so \linewidth is constrained.
        varwidth_opt = ""
        wrapped_content = (
            r"\begin{minipage}{" + textwidth + r"}" + "\n"
            + table_latex + "\n"
            + r"\end{minipage}"
        )
    else:
        # For regular tables: use varwidth for natural sizing
        varwidth_opt = r"varwidth=\maxdimen"
        wrapped_content = table_latex

    standalone_doc = (
        standalone_template.replace("VARWIDTH_OPTION", varwidth_opt)
        .replace("TEXTWIDTH_PLACEHOLDER", textwidth)
        .replace("TABLE_CONTENT_PLACEHOLDER", wrapped_content)
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_file = os.path.join(tmpdir, "table.tex")
        pdf_file = os.path.join(tmpdir, "table.pdf")

        with open(tex_file, "w") as f:
            f.write(standalone_doc)

        # Compile LaTeX → PDF
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, tex_file],
            capture_output=True,
        )

        if not os.path.exists(pdf_file):
            print(f"    [-] LaTeX compilation failed.")
            # Show last 15 lines of log for debugging
            log_file = os.path.join(tmpdir, "table.log")
            if os.path.exists(log_file):
                with open(log_file) as lf:
                    lines = lf.readlines()
                    for line in lines[-15:]:
                        print(f"        {line.rstrip()}")
            return False

        # Convert PDF → PNG using sips (macOS) or pdftoppm/convert
        # Try pdftoppm first (poppler), then sips (macOS built-in)
        output_path = Path(output_png)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if _has_command("pdftoppm"):
            # pdftoppm produces <prefix>-1.png so we use a temp prefix
            prefix = os.path.join(tmpdir, "out")
            subprocess.run(
                ["pdftoppm", "-png", "-r", str(dpi), "-singlefile", pdf_file, prefix],
                capture_output=True,
            )
            tmp_png = prefix + ".png"
            if os.path.exists(tmp_png):
                _copy_file(tmp_png, str(output_path))
                return True

        if _has_command("magick"):
            # ImageMagick 7+
            subprocess.run(
                ["magick", "-density", str(dpi), pdf_file, "-flatten", "-quality", "100", str(output_path)],
                capture_output=True,
            )
            if output_path.exists() and output_path.stat().st_size > 0:
                return True

        if _has_command("convert"):
            # ImageMagick 6
            subprocess.run(
                ["convert", "-density", str(dpi), pdf_file, "-flatten", "-quality", "100", str(output_path)],
                capture_output=True,
            )
            if output_path.exists() and output_path.stat().st_size > 0:
                return True

        if _has_command("sips"):
            # macOS built-in – limited DPI control but works
            subprocess.run(
                ["sips", "-s", "format", "png", pdf_file, "--out", str(output_path)],
                capture_output=True,
            )
            if output_path.exists() and output_path.stat().st_size > 0:
                return True

        print(f"    [-] No PDF-to-PNG converter found. Install poppler (pdftoppm) or ImageMagick.")
        return False


def _has_command(cmd):
    """Check if a command is available on PATH."""
    try:
        subprocess.run([cmd, "--version"], capture_output=True)
        return True
    except FileNotFoundError:
        return False


def _copy_file(src, dst):
    """Simple file copy."""
    with open(src, "rb") as f:
        data = f.read()
    with open(dst, "wb") as f:
        f.write(data)


def main():
    parser = argparse.ArgumentParser(
        description="Extract LaTeX tables from a .tex file and render as PNG images."
    )
    parser.add_argument("-t", "--tex", required=True, help="Input .tex file")
    parser.add_argument("-o", "--output", required=True, help="Output directory for PNGs")
    parser.add_argument("--dpi", type=int, default=300, help="PNG resolution (default: 300)")
    parser.add_argument(
        "--textwidth",
        default="14.5cm",
        help="LaTeX text width for tabularx (default: 14.5cm)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.tex):
        print(f"Error: File {args.tex} not found.")
        sys.exit(1)

    tables = extract_tables(args.tex)
    if not tables:
        print("No tables found in the input file.")
        sys.exit(0)

    print(f"[*] Found {len(tables)} table(s) in {args.tex}")

    success_count = 0
    for tbl in tables:
        out_png = os.path.join(args.output, f"{tbl['slug']}.png")
        print(f"[*] Table {tbl['index']}: \"{tbl['caption']}\"")
        print(f"    → {out_png}")

        ok = render_table_to_png(
            tbl["content"],
            out_png,
            dpi=args.dpi,
            textwidth=args.textwidth,
        )
        if ok:
            print(f"    [+] Success!")
            success_count += 1
        else:
            print(f"    [-] Failed to render.")

    print(f"\n[*] Done: {success_count}/{len(tables)} tables rendered.")


if __name__ == "__main__":
    main()
