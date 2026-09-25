import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

def find_drawio_executable():
    """Locates the Draw.io executable.

    Resolution order:
    1. DRAWIO environment variable (set by the nix shellHook on macOS,
       where the nix package ships an app bundle instead of a PATH binary)
    2. `drawio` / `draw.io` on PATH (nix env on Linux, manual installs)
    3. Standard macOS app bundle location
    """
    env_path = os.environ.get("DRAWIO")
    if env_path and os.path.exists(env_path):
        return env_path

    for name in ("drawio", "draw.io"):
        exe = shutil.which(name)
        if exe:
            return exe

    mac_path = "/Applications/draw.io.app/Contents/MacOS/draw.io"
    if os.path.exists(mac_path):
        return mac_path

    return None

def convert_drawio_to_pdf(input_xml, output_dir):
    input_path = Path(input_xml)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    drawio_exe = find_drawio_executable()
    if not drawio_exe:
        print("Error: Draw.io not found.")
        print("Enter the nix dev shell (`nix develop`) so drawio is on PATH.")
        sys.exit(1)

    # Setup target path
    final_pdf = output_path / f"{input_path.stem}.pdf"

    print(f"[*] Processing: {input_path}")

    try:
        # We export DIRECTLY to PDF.
        # --crop ensures the PDF is the size of the diagram, not a full A4 page.
        # This preserves text as vector data (selectable/searchable).
        cmd = [
            drawio_exe,
            "--export",
            "--format", "pdf",
            "--crop",
            "--output", str(final_pdf),
            str(input_path)
        ]

        if sys.platform.startswith("linux"):
            # Electron's chromium sandbox often fails in nix shells / CI.
            cmd.append("--no-sandbox")
            # Without a display server, run under a virtual X server.
            if not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
                cmd = ["xvfb-run", "-a"] + cmd
        elif sys.platform == "darwin":
            # The nix-built app is ad-hoc signed, so macOS Keychain would
            # prompt for access ("draw.io wants to use your confidential
            # information...") on every launch. Skip the Keychain entirely.
            cmd.append("--use-mock-keychain")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and final_pdf.exists():
            print(f"[+] Success! Selectable PDF created at: {final_pdf}")
        else:
            print(f"[-] Draw.io Error: {result.stderr}")
            sys.exit(1)

    except Exception as e:
        print(f"[-] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Draw.io XML to Searchable PDF.")
    parser.add_argument("-d", "--drawio", required=True, help="Input XML file")
    parser.add_argument("-o", "--output", required=True, help="Output directory")

    args = parser.parse_args()

    if not os.path.exists(args.drawio):
        print(f"Error: File {args.drawio} not found.")
        sys.exit(1)

    convert_drawio_to_pdf(args.drawio, args.output)
