---
name: jupyter-plotly-slides
description: "Build interactive slide decks from Jupyter notebooks with live Plotly figures. Use whenever the user wants a presentation, deck, slide show, walkthrough, or readout that includes Plotly charts — especially when they mention nbconvert, reveal.js, RISE, slideshow, or want an alternative to PowerPoint that keeps charts interactive (hover, zoom, pan). Also trigger when the user is working in a .ipynb and asks to present, share, or turn the notebook into slides. Bundles a slide-tagger that sets cell metadata (which Jupyter MCP can't write directly) and a build wrapper that wires up nbconvert with sane Plotly-compatible defaults."
---

# Jupyter + Plotly Slide Decks

Turn a Jupyter notebook into an interactive reveal.js slide deck where Plotly figures stay live — hover, zoom, pan, all of it. The deck is a single self-contained `.slides.html` you can open in a browser, host anywhere, or screen-share.

This skill is for **interactive, code-adjacent decks**: analysis walkthroughs, model demos, internal readouts where the audience may want to poke at a chart. For polished, external-facing slides built against a corporate template, a python-pptx workflow is the better tool — the two approaches are complementary, not rivals.

## How a deck is built

1. **Notebook with tagged cells.** Each cell carries a `slideshow.slide_type` metadata field telling reveal.js where it belongs in the deck.
2. **Plotly renderer set to `notebook_connected`.** This is the only renderer that survives nbconvert and produces a standalone HTML — the default `notebook` renderer needs Jupyter's live extension JS and goes blank in static slides.
3. **`jupyter nbconvert --to slides`** turns the notebook into reveal.js HTML.
4. Optionally serve with `--post serve` to preview in-browser with auto-reload.

The slide tags are the part Jupyter MCP can't set directly, so the bundled `tag_slides.py` is doing real work — don't write your own.

## Workflow

### 1. Author or open the notebook

If starting fresh, use `scripts/init_notebook.py` to scaffold one with the right imports and Plotly renderer already wired up:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/init_notebook.py --output my-deck.ipynb --title "My Deck"
```

If the user already has an analysis notebook they want to convert, just open it and skip to tagging.

### 2. Tag cells with slide types

Slide types and what they mean:

| `slide_type`   | Effect in reveal.js |
|----------------|---------------------|
| `slide`        | New horizontal slide |
| `subslide`     | Vertical child of the current slide (audience presses ↓) |
| `fragment`     | Appears on next click within the parent slide |
| `skip`         | Excluded from the deck entirely |
| `notes`        | Speaker notes (visible only in speaker view, `s` key) |
| *(unset)*      | Continues the current slide |

Two ways to apply tags:

**Auto-tag from headings** (recommended starting point):

```bash
python ${CLAUDE_SKILL_DIR}/scripts/tag_slides.py my-deck.ipynb --auto
```

This walks the notebook and applies:
- Markdown cell starting with `# ` → `slide`
- Markdown cell starting with `## ` → `subslide`
- Code cells → no tag (continues parent slide)
- Markdown cells starting with `<!-- skip -->` → `skip`
- Markdown cells starting with `<!-- notes -->` → `notes`

Auto-tagging is overwritable; if you want explicit control, follow it up with a manifest.

**Manifest** (explicit per-cell control):

```bash
python ${CLAUDE_SKILL_DIR}/scripts/tag_slides.py my-deck.ipynb --manifest tags.json
```

Where `tags.json` is `{"0": "slide", "3": "subslide", "5": "fragment", "7": "skip"}` — keys are cell indices, values are slide types. Cells not listed are left alone.

For deeper detail on slide types and layout, read `references/slide-anatomy.md`.

### 3. Plotly figures: use the slide-friendly defaults

Inside the notebook, set this once near the top (the init script already does it):

```python
import plotly.io as pio
pio.renderers.default = "notebook_connected"
```

For each figure, set explicit dimensions that fit reveal's slide container (defaults: 960×700):

```python
fig.update_layout(width=900, height=520, margin=dict(l=40, r=40, t=60, b=40))
fig.show()
```

Why not `autosize=True`? Reveal slides have a fixed container; autosize gets cropped or floats to one side. Pin the dimensions and you control the result.

For more on renderers, themes, and common Plotly-in-slides gotchas, read `references/plotly-in-slides.md`.

### 4. Build the deck

```bash
python ${CLAUDE_SKILL_DIR}/scripts/build_slides.py my-deck.ipynb
```

This wraps `nbconvert --to slides` with these defaults:
- Theme: `white` (clean, prints well, suits data work)
- Transition: `none` (no flip distraction)
- `--SlidesExporter.reveal_scroll=True` (long slides scroll instead of clipping)

Common variants:

```bash
# Hide code cells (for non-technical audience)
python ${CLAUDE_SKILL_DIR}/scripts/build_slides.py my-deck.ipynb --no-input

# Live-preview with auto-reload
python ${CLAUDE_SKILL_DIR}/scripts/build_slides.py my-deck.ipynb --serve

# Different theme (white | black | league | beige | sky | night | serif | simple | solarized)
python ${CLAUDE_SKILL_DIR}/scripts/build_slides.py my-deck.ipynb --theme night
```

The output is `my-deck.slides.html` in the same directory as the notebook.

### 5. Verify

Open the `.slides.html` in a browser. Check that:
- Each `slide` cell starts a new slide (arrows or space to navigate).
- Plotly figures render and are interactive (hover should show tooltips).
- No cells you meant to `skip` appear.
- Long content scrolls within the slide rather than overflowing.

If figures are blank, the renderer is wrong (see `references/plotly-in-slides.md`).

## Common patterns

### Analysis readout (15-25 slides)

- Title slide (markdown, `slide`)
- Question/motivation (markdown, `slide`)
- Methodology overview (markdown, `slide`) + 2-3 detail subslides
- Findings: one `slide` per major finding, with the supporting chart as the next code cell (no tag, so it lands on the same slide as its heading)
- Caveats (markdown, `slide`)
- Recommendations (markdown, `slide`)

### Demo (5-10 slides)

- Hook (markdown, `slide`)
- Live chart that the audience pokes at (code, no tag — continues the hook slide so the chart sits under the framing)
- Variations as `fragment` cells: each click reveals a new filter or breakdown
- "How it works" detail in `notes` cells for the speaker

## Constraints worth knowing

- **No live code execution in the slides.** The `.slides.html` is static — cell outputs are baked in at build time. Re-run the notebook before re-building if your data changed.
- **Plotly figures need to be `.show()`'d, not just declared.** A bare `fig` as the last expression won't render reliably in the static export; `fig.show()` does.
- **Output isn't editable in PowerPoint.** This skill produces HTML. If the audience needs `.pptx`, use the `presentation` skill instead and consider screenshotting key plotly views in.
- **Speaker view requires the live server.** Press `s` while served via `--serve`; the static HTML supports it too but only when opened from a server (not `file://` in some browsers).

## When NOT to use this skill

- Static, polished decks for external stakeholders → use `presentation` (python-pptx) instead.
- Dashboards with parameter controls users adjust → use Streamlit or Plotly Dash.
- A single chart shared in Slack → just `fig.write_html(...)` and attach.
