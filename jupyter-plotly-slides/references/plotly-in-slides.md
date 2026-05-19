# Plotly inside reveal.js slides

Three things matter: the renderer, the figure size, and the theme. Get all three right and figures look the same in the deck as they do in the notebook.

## Renderer: must be `_connected`

```python
import plotly.io as pio
pio.renderers.default = "notebook_connected"
```

Plotly figures are rendered by client-side JavaScript. The default `"notebook"` renderer assumes Jupyter's plotly extension is loaded in the page — true in a live notebook, false in nbconvert's static HTML. Result: figures vanish, leaving blank space where charts should be.

The `_connected` variants pull `plotly.js` from a CDN, so the slide HTML is self-sufficient. Two flavors:

| Renderer               | When to use |
|------------------------|-------------|
| `notebook_connected`   | Default. Figures share the page's CSS context, smaller HTML, works for almost everything. |
| `iframe_connected`     | Use when reveal's CSS interferes with your figures (rare). Each figure gets its own iframe. Larger HTML, but isolated. |

If the audience will be offline, swap to the non-connected version *after* downloading plotly.js into the same directory and patching the script tag — usually not worth the trouble; just keep them online.

## Size: pin width and height, don't autosize

Reveal's slide container is fixed (~960×700 by default). Plotly's `autosize=True` queries its parent container at render time — but inside reveal, the parent's dimensions aren't always settled when the figure draws, so you get inconsistent results: figures cropped, floating left, or full-bleed.

Set explicit dimensions that leave room for a title and breathing space:

```python
fig.update_layout(
    width=900, height=520,
    margin=dict(l=40, r=40, t=60, b=40),
)
```

This leaves ~30px on each side and ~90px for the slide title above (if you have one). Adjust if the figure has long axis labels (more margin) or no title (less top margin).

## `fig.show()`, not bare `fig`

A bare `fig` as the last expression of a code cell *looks* like it renders in the notebook because Jupyter calls `_repr_mimebundle_` on it. That mimebundle includes a `text/html` part with the Plotly HTML, and nbconvert often does pick it up — but inconsistently, depending on plotly version and how the cell was last executed.

`fig.show()` explicitly emits the display output and is robust across versions. Use it.

## Themes that read on slides

The default Plotly template (`plotly`) has a light-gray gridded background that can fight reveal's `white` theme. Better options for slides:

```python
fig.update_layout(template="simple_white")     # clean, presentation-ready
fig.update_layout(template="plotly_white")     # default but with white bg
fig.update_layout(template="seaborn")          # softer, good for many series
```

Pair with reveal:

| Reveal theme | Plotly template that pairs cleanly |
|--------------|-------------------------------------|
| `white`      | `simple_white` or `plotly_white`    |
| `night`/`black` | `plotly_dark`                    |
| `serif`      | `simple_white`                      |

Set the template once at the top of the notebook (`pio.templates.default = "simple_white"`) so every figure picks it up.

## Font size: charts are smaller than you think

Slides are viewed from across a room. Axis labels at 12pt — fine in a notebook — are unreadable on a projector.

```python
fig.update_layout(
    font=dict(size=14),
    title=dict(font=dict(size=18)),
    xaxis=dict(tickfont=dict(size=12)),
    yaxis=dict(tickfont=dict(size=12)),
)
```

Test by zooming the browser to ~50% — if you can still read it, the back row can too.

## Multiple figures per slide

Inside one slide, two `fig.show()` calls stack vertically. To put two charts side-by-side:

- **Single figure with subplots** (preferred). Use `plotly.subplots.make_subplots(rows=1, cols=2)`. Width still ~900; each subplot gets ~440.
- **HTML row** (advanced). Wrap each `fig.to_html(include_plotlyjs=False)` call in a flex container. Brittle; only do this if subplots can't represent what you want.

## Tables, dataframes, images

- Pandas DataFrames render as HTML tables. Keep them small (≤8 rows × 6 cols) or they overflow.
- Use `df.style.background_gradient(...)` for heatmap-style tables — they read well on slides.
- Static images (PNGs, screenshots) embed cleanly. Reference them with `![](path.png)` in markdown; if the slide will be opened elsewhere, build with `--embed_images=True` (the default in `build_slides.py`).

## Common failure modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Figure is blank | Wrong renderer | Set `pio.renderers.default = "notebook_connected"` and re-run the cell |
| Figure floats to the left | `autosize=True` and slide container not measured yet | Pin `width=`/`height=` |
| Figure overflows slide bottom | `height` too big or scroll disabled | Reduce to 520, or rely on `reveal_scroll=True` (default in `build_slides.py`) |
| Hover tooltips don't appear | Browser opened the file via `file://` and CDN blocked | Serve via `--serve` or host the file |
| Figures appear, then vanish on transition | Reveal's CSS hides off-screen slides; plotly's resize observer fires late | Use `iframe_connected` renderer |
