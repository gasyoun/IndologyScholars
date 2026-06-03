"""Mobility page generator — delegates to the pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generate_publication_pages import generate_mobility_page

if __name__ == "__main__":
    generate_mobility_page()
    print("findings/mobility.html generated")
