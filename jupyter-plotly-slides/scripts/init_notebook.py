"""Create a starter notebook wired for the jupyter-plotly-slides workflow.

The output notebook has:
- A first markdown cell tagged `slide` with the title
- A setup code cell that sets the Plotly renderer to `notebook_connected`
  and imports common libraries, with no slide tag (lives inside title slide)
- A second markdown cell tagged `slide` for the first section
- A starter Plotly figure cell with reveal-friendly sizing

Usage:
    python init_notebook.py --output deck.ipynb --title "My Deck"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


SLIDESHOW = "slideshow"
SLIDE_TYPE = "slide_type"


def tag(cell, slide_type: str) -> None:
    cell.metadata[SLIDESHOW] = {SLIDE_TYPE: slide_type}


def build_notebook(title: str) -> nbformat.NotebookNode:
    nb = new_notebook()

    title_md = new_markdown_cell(f"# {title}\n\n*Subtitle or one-liner here*")
    tag(title_md, "slide")

    setup = new_code_cell(
        "import plotly.express as px\n"
        "import plotly.graph_objects as go\n"
        "import plotly.io as pio\n"
        "\n"
        "pio.renderers.default = \"notebook_connected\"\n"
        "\n"
        "SLIDE_W, SLIDE_H = 900, 520\n"
        "SLIDE_MARGIN = dict(l=40, r=40, t=60, b=40)\n"
    )

    section_md = new_markdown_cell("# First section\n\nHeadline framing the chart below.")
    tag(section_md, "slide")

    chart = new_code_cell(
        "df = px.data.gapminder().query(\"year == 2007\")\n"
        "fig = px.scatter(df, x=\"gdpPercap\", y=\"lifeExp\", color=\"continent\",\n"
        "                 size=\"pop\", hover_name=\"country\", log_x=True,\n"
        "                 title=\"GDP vs. life expectancy, 2007\")\n"
        "fig.update_layout(width=SLIDE_W, height=SLIDE_H, margin=SLIDE_MARGIN)\n"
        "fig.show()\n"
    )

    notes = new_markdown_cell(
        "<!-- notes -->\n"
        "Speaker notes for this slide. Press `s` in the deck to see them.\n"
    )
    tag(notes, "notes")

    nb.cells = [title_md, setup, section_md, chart, notes]
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    return nb


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, help="Path for the new .ipynb")
    p.add_argument("--title", default="Untitled Deck", help="Title for the first slide")
    args = p.parse_args()

    out = Path(args.output)
    if out.exists():
        print(f"refusing to overwrite existing file: {out}", file=sys.stderr)
        return 1

    nb = build_notebook(args.title)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
