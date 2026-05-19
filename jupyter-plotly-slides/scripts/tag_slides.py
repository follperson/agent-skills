"""Set `slideshow.slide_type` metadata on notebook cells.

Two modes:

  --auto       Apply tags from markdown heading conventions:
                 `# ...`              -> slide
                 `## ...`             -> subslide
                 `<!-- skip -->...`   -> skip
                 `<!-- notes -->...`  -> notes
                 Code cells: left untagged (continue parent slide).

  --manifest FILE   Apply tags from a JSON object mapping cell index (str)
                    to slide_type. Cells not listed are left unchanged.

Modes compose: run --auto, then --manifest to override specific cells.

Usage:
    python tag_slides.py deck.ipynb --auto
    python tag_slides.py deck.ipynb --manifest tags.json
    python tag_slides.py deck.ipynb --auto --manifest tags.json
    python tag_slides.py deck.ipynb --show           # print current tags
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import nbformat


VALID_TYPES = {"slide", "subslide", "fragment", "skip", "notes", ""}
SLIDESHOW = "slideshow"
SLIDE_TYPE = "slide_type"


def get_tag(cell) -> str:
    return cell.metadata.get(SLIDESHOW, {}).get(SLIDE_TYPE, "")


def set_tag(cell, slide_type: str) -> None:
    if slide_type not in VALID_TYPES:
        raise ValueError(
            f"invalid slide_type {slide_type!r}; must be one of {sorted(VALID_TYPES)}"
        )
    if slide_type == "":
        if SLIDESHOW in cell.metadata:
            cell.metadata[SLIDESHOW].pop(SLIDE_TYPE, None)
            if not cell.metadata[SLIDESHOW]:
                del cell.metadata[SLIDESHOW]
    else:
        cell.metadata[SLIDESHOW] = {SLIDE_TYPE: slide_type}


def auto_tag(cell) -> str | None:
    """Return the slide_type implied by cell content, or None to leave alone."""
    if cell.cell_type != "markdown":
        return None
    src = cell.source.lstrip()
    if src.startswith("<!-- skip -->"):
        return "skip"
    if src.startswith("<!-- notes -->"):
        return "notes"
    first_line = src.splitlines()[0] if src else ""
    if re.match(r"^#\s+\S", first_line):
        return "slide"
    if re.match(r"^##\s+\S", first_line):
        return "subslide"
    return None


def apply_auto(nb) -> int:
    changed = 0
    for cell in nb.cells:
        suggested = auto_tag(cell)
        if suggested is not None and get_tag(cell) != suggested:
            set_tag(cell, suggested)
            changed += 1
    return changed


def apply_manifest(nb, manifest: dict[str, str]) -> int:
    changed = 0
    for idx_str, slide_type in manifest.items():
        idx = int(idx_str)
        if not 0 <= idx < len(nb.cells):
            raise IndexError(f"cell index {idx} out of range (notebook has {len(nb.cells)} cells)")
        if get_tag(nb.cells[idx]) != slide_type:
            set_tag(nb.cells[idx], slide_type)
            changed += 1
    return changed


def show(nb) -> None:
    for i, cell in enumerate(nb.cells):
        tag = get_tag(cell) or "-"
        preview = cell.source.replace("\n", " ⏎ ")[:70]
        print(f"  [{i:>3}] {cell.cell_type:<8} {tag:<9} {preview}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("notebook", help="Path to .ipynb")
    p.add_argument("--auto", action="store_true", help="Tag from heading conventions")
    p.add_argument("--manifest", help="JSON file: {cell_index: slide_type}")
    p.add_argument("--show", action="store_true", help="Print current tags and exit")
    p.add_argument("--dry-run", action="store_true", help="Don't write changes")
    args = p.parse_args()

    nb_path = Path(args.notebook)
    nb = nbformat.read(nb_path, as_version=4)

    if args.show:
        show(nb)
        return 0

    changed = 0
    if args.auto:
        changed += apply_auto(nb)
    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text())
        changed += apply_manifest(nb, manifest)

    if not (args.auto or args.manifest):
        p.error("specify --auto, --manifest, or --show")

    if args.dry_run:
        print(f"would change {changed} cell(s); --dry-run, not writing")
        show(nb)
        return 0

    if changed:
        nbformat.write(nb, nb_path)
    print(f"updated {changed} cell(s) in {nb_path}")
    show(nb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
