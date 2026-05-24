"""Build a submission-grade DOCX of ppv_draft.md with working figures.

Pandoc does not embed SVG into DOCX, so the hand-written SVG figures must be
rasterised to PNG first. ImageMagick (`magick`) is used for conversion. A temp
markdown copy with .svg -> .png image links is written, then pandoc compiles it.

Requires: pandoc, ImageMagick (`magick`) on PATH.
Usage:  python article/build_docx.py
"""
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "ppv_draft.md")
TMP_MD = os.path.join(HERE, "_ppv_draft_docx.md")
OUT_DOCX = os.path.join(HERE, "ppv_draft.docx")
DENSITY = "150"

IMG_RE = re.compile(r"(!\[[^\]]*\]\()([^)]+\.svg)(\))")


def convert_svg(rel_path):
    """Convert one SVG (path relative to article/) to a sibling PNG. Return rel png path."""
    svg_abs = os.path.normpath(os.path.join(HERE, rel_path))
    png_abs = os.path.splitext(svg_abs)[0] + ".png"
    if not os.path.exists(svg_abs):
        print(f"  MISSING svg: {rel_path}")
        return None
    subprocess.run(
        ["magick", "-density", DENSITY, "-background", "white", svg_abs, png_abs],
        check=True,
    )
    return os.path.splitext(rel_path)[0] + ".png"


def main():
    if not shutil.which("magick"):
        sys.exit("ERROR: ImageMagick (`magick`) not found on PATH.")
    if not shutil.which("pandoc"):
        sys.exit("ERROR: pandoc not found on PATH.")

    with open(SRC, encoding="utf-8") as f:
        text = f.read()

    converted = set()

    def repl(m):
        rel = m.group(2)
        png = convert_svg(rel)
        if png:
            converted.add(rel)
            return m.group(1) + png + m.group(3)
        return m.group(0)  # leave untouched if missing

    new_text = IMG_RE.sub(repl, text)
    print(f"Converted {len(converted)} SVG figure(s) to PNG.")

    with open(TMP_MD, "w", encoding="utf-8") as f:
        f.write(new_text)

    # Run pandoc from article/ so relative image paths resolve.
    subprocess.run(
        ["pandoc", os.path.basename(TMP_MD), "-o", os.path.basename(OUT_DOCX),
         "--toc", "--toc-depth=2"],
        cwd=HERE, check=True,
    )
    os.remove(TMP_MD)
    size = os.path.getsize(OUT_DOCX)
    print(f"Built {OUT_DOCX} ({size:,} bytes)")


if __name__ == "__main__":
    main()
