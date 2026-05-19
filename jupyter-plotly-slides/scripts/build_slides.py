"""Build a reveal.js slide deck from a notebook via nbconvert.

Defaults that differ from raw `nbconvert --to slides`:
  - theme:      white       (clean, suits data work, prints OK)
  - transition: none        (no flip distraction between slides)
  - scroll:     true        (long slides scroll instead of clipping)
  - embed_images: true      (single self-contained HTML, no external image deps)

Usage:
    python build_slides.py deck.ipynb
    python build_slides.py deck.ipynb --no-input
    python build_slides.py deck.ipynb --serve
    python build_slides.py deck.ipynb --theme night --transition fade
    python build_slides.py deck.ipynb --output-dir build/

Themes:      white | black | league | beige | sky | night | serif | simple | solarized
Transitions: none | fade | slide | convex | concave | zoom
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


THEMES = {"white", "black", "league", "beige", "sky", "night", "serif", "simple", "solarized"}
TRANSITIONS = {"none", "fade", "slide", "convex", "concave", "zoom"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("notebook", help="Path to .ipynb")
    p.add_argument("--theme", default="white", choices=sorted(THEMES))
    p.add_argument("--transition", default="none", choices=sorted(TRANSITIONS))
    p.add_argument("--no-input", action="store_true",
                   help="Hide code cells (for non-technical audience)")
    p.add_argument("--serve", action="store_true",
                   help="Serve and open in browser with auto-reload")
    p.add_argument("--output-dir", help="Directory for .slides.html (default: alongside notebook)")
    p.add_argument("--no-scroll", action="store_true",
                   help="Disable per-slide scrolling (slides will clip on overflow)")
    args = p.parse_args()

    nb = Path(args.notebook).resolve()
    if not nb.exists():
        print(f"notebook not found: {nb}", file=sys.stderr)
        return 1

    cmd = [
        "jupyter", "nbconvert",
        "--to", "slides",
        str(nb),
        f"--SlidesExporter.reveal_theme={args.theme}",
        f"--SlidesExporter.reveal_transition={args.transition}",
        f"--SlidesExporter.reveal_scroll={'False' if args.no_scroll else 'True'}",
        "--SlidesExporter.embed_images=True",
    ]
    if args.no_input:
        cmd.append("--no-input")
    if args.output_dir:
        out_dir = Path(args.output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd += ["--output-dir", str(out_dir)]
    if args.serve:
        cmd.append("--post=serve")

    print("running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
