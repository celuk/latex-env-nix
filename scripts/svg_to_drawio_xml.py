import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

def parse_svg_length(value):
    """Parses SVG length strings like '120', '120px', '8.5in' into pixels."""
    if not value:
        return None

    match = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z%]*)\s*", value)
    if not match:
        return None

    number = float(match.group(1))
    unit = match.group(2).lower()

    # Draw.io works naturally with px-like units; convert common physical units.
    unit_to_px = {
        "": 1.0,
        "px": 1.0,
        "pt": 96.0 / 72.0,
        "pc": 16.0,
        "mm": 96.0 / 25.4,
        "cm": 96.0 / 2.54,
        "in": 96.0,
    }

    if unit in unit_to_px:
        return number * unit_to_px[unit]

    return None


def get_svg_dimensions(svg_path):
    """Gets width/height from SVG attributes or falls back to viewBox."""
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except ET.ParseError:
        return 800.0, 600.0

    width = parse_svg_length(root.attrib.get("width"))
    height = parse_svg_length(root.attrib.get("height"))

    if width and height:
        return width, height

    view_box = root.attrib.get("viewBox", "").strip()
    if view_box:
        parts = re.split(r"[\s,]+", view_box)
        if len(parts) == 4:
            try:
                vb_width = float(parts[2])
                vb_height = float(parts[3])
                if vb_width > 0 and vb_height > 0:
                    return vb_width, vb_height
            except ValueError:
                pass

    return 800.0, 600.0


def analyze_svg_text(svg_path):
    """Inspects text nodes and detects private-use glyph encoding in SVG text."""
    svg_ns = "{http://www.w3.org/2000/svg}"
    stats = {
        "text_nodes": 0,
        "tspan_nodes": 0,
        "text_chars": 0,
        "private_use_chars": 0,
    }

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except ET.ParseError:
        return stats

    text_nodes = root.findall(f".//{svg_ns}text")
    tspan_nodes = root.findall(f".//{svg_ns}tspan")
    stats["text_nodes"] = len(text_nodes)
    stats["tspan_nodes"] = len(tspan_nodes)

    chars = []
    for node in tspan_nodes:
        if node.text:
            chars.append(node.text)
    if not chars:
        for node in text_nodes:
            if node.text:
                chars.append(node.text)

    all_text = "".join(chars)
    stats["text_chars"] = len(all_text)
    stats["private_use_chars"] = sum(
        1 for ch in all_text if 0xE000 <= ord(ch) <= 0xF8FF
    )

    return stats


def convert_svg_to_drawio_xml(input_svg, output_dir):
    input_path = Path(input_svg)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    final_xml = output_path / f"{input_path.stem}.xml"

    print(f"[*] Processing: {input_path}")

    try:
        svg_content = input_path.read_text(encoding="utf-8")
        # Draw.io style values are separated by ';'.
        # Using data:image/svg+xml;base64,... introduces ';base64,' which breaks parsing.
        # URL-encoding avoids semicolons in the data URI and renders correctly in exports.
        svg_encoded = quote(svg_content, safe="")
        width, height = get_svg_dimensions(str(input_path))
        text_stats = analyze_svg_text(str(input_path))

        if text_stats["text_nodes"] > 0:
            print(
                "[!] Note: This converter embeds the SVG as a single image cell in Draw.io."
            )
            print(
                "[!] Text is not converted into native Draw.io text cells, so editability/selectability depends on SVG font encoding."
            )

        if text_stats["text_chars"] > 0:
            pua_ratio = text_stats["private_use_chars"] / text_stats["text_chars"]
            if pua_ratio > 0.5:
                print(
                    "[!] Warning: SVG text uses mostly private-use Unicode glyphs (custom embedded font mapping)."
                )
                print(
                    "[!] Copy/paste from exported PDFs may appear as unknown characters even though text objects exist."
                )

        mx_graph_model = ET.Element(
            "mxGraphModel",
            {
                "dx": "1426",
                "dy": "827",
                "grid": "1",
                "gridSize": "10",
                "guides": "1",
                "tooltips": "1",
                "connect": "1",
                "arrows": "1",
                "fold": "1",
                "page": "1",
                "pageScale": "1",
                "pageWidth": "850",
                "pageHeight": "1100",
                "math": "0",
                "shadow": "0",
            },
        )

        root = ET.SubElement(mx_graph_model, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

        image_style = (
            "shape=image;"
            "html=1;"
            "imageAspect=1;"
            "aspect=fixed;"
            "verticalLabelPosition=bottom;"
            "verticalAlign=top;"
            f"image=data:image/svg+xml,{svg_encoded};"
        )

        image_cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": "2",
                "value": "",
                "style": image_style,
                "vertex": "1",
                "parent": "1",
            },
        )

        ET.SubElement(
            image_cell,
            "mxGeometry",
            {
                "x": "0",
                "y": "0",
                "width": f"{width:.2f}",
                "height": f"{height:.2f}",
                "as": "geometry",
            },
        )

        ET.indent(mx_graph_model, space="  ")
        xml_content = ET.tostring(mx_graph_model, encoding="unicode", method="xml")
        final_xml.write_text(xml_content + "\n", encoding="utf-8")

        print(f"[+] Success! Draw.io XML created at: {final_xml}")

    except Exception as err:
        print(f"[-] Error: {err}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert SVG to Draw.io mxGraphModel XML."
    )
    parser.add_argument(
        "-s",
        "--svg",
        "-d",
        "--drawio",
        dest="svg",
        required=True,
        help="Input SVG file (supports legacy -d/--drawio style)",
    )
    parser.add_argument("-o", "--output", required=True, help="Output directory")

    args = parser.parse_args()

    if not os.path.exists(args.svg):
        print(f"Error: File {args.svg} not found.")
        sys.exit(1)

    convert_svg_to_drawio_xml(args.svg, args.output)
