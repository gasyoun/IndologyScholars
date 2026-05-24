"""Export submission-grade figures for ППВ: separate ≥300 dpi JPEGs + captions list.

ППВ requires illustrations as separate TIFF/JPEG/PSD/EPS files at >=300 dpi with
a list of captions. This parses the figure references + captions out of
ppv_draft.md, rasterises each SVG at 300 dpi via ImageMagick, and writes them to
article/figures_submission/ together with captions.txt.

Usage:  python article/export_figures_submission.py
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "ppv_draft.md")
OUT = os.path.join(HERE, "figures_submission")
DENSITY = "300"

# ![caption](path.svg)
FIG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+\.svg)\)")


def main():
    os.makedirs(OUT, exist_ok=True)
    text = open(SRC, encoding="utf-8").read()
    captions = []
    n = 0
    for caption, rel in FIG_RE.findall(text):
        svg_abs = os.path.normpath(os.path.join(HERE, rel))
        if not os.path.exists(svg_abs):
            print(f"  MISSING: {rel}")
            continue
        n += 1
        base = os.path.splitext(os.path.basename(rel))[0]
        jpg = os.path.join(OUT, f"{base}.jpg")
        subprocess.run(
            ["magick", "-density", DENSITY, "-background", "white",
             svg_abs, "-quality", "92", jpg],
            check=True,
        )
        captions.append(f"{base}.jpg\t{caption}")
        print(f"  [{n}] {base}.jpg  <- {rel}")
    with open(os.path.join(OUT, "captions.txt"), "w", encoding="utf-8") as f:
        f.write("Список иллюстраций (файл\tподпись)\n\n")
        f.write("\n".join(captions) + "\n")
    print(f"Exported {n} figure(s) at {DENSITY} dpi to {OUT}")


if __name__ == "__main__":
    main()
