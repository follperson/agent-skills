---
name: pandas-styler-tables
description: "Style and format pandas DataFrames in Jupyter notebooks using df.style. Use when displaying a DataFrame as the primary artifact and visual treatment helps the reader — heatmaps, currency/percent formatting, diverging palettes for deltas, conditional row/cell highlighting, polished tables for handoff. Covers both exploratory tables (gradients, highlight_max for fast pattern-finding) and stakeholder-facing findings (formatted numbers, captions, header treatment). Includes a discovery step that looks for project-specific style specs in CLAUDE.md, project docs, user memory, and sibling notebooks before falling back to defaults. Triggers: df.style, styler, format dataframe, color cells, highlight rows, table heatmap, currency table, percent table, conditional formatting, polish this table, make this table readable, show divergence between, KPI table, background_gradient, set_table_styles, applymap with CSS, highlight_max, divergent palette, center coloring at zero."
---

# Pandas Styler Tables

Make the table do the reader's work: gradients for magnitude, diverging palettes for direction, formatted numbers so nobody counts digits. Two modes:

- **Exploratory** — fast pattern-finding in your own notebook. Gradient, `highlight_max`, in-cell bars. Skip captions and polish.
- **Findings** — handoff for stakeholders. Formatted numbers, a caption, header CSS, emphasis tied to the story.

The **Fast path** below covers most tasks with nothing but this file. Open a reference only for the edge case it names — reading three reference files to format one table is the failure mode this skill exists to prevent.

## Is Styler even the right tool?

| Situation | Use |
|-----------|-----|
| Table is the primary artifact AND <~100 rows | **Styler** |
| Reader needs to sort/filter/search interactively | `itables` |
| Publication-grade (paper, deck, PDF) with stub/spanner/footnote | `great_tables` |
| >100 rows AND hunting for patterns | a heatmap chart (`px.imshow` / seaborn) |
| Just a structural peek (`.head()`, `.info()`, `.describe()`) | plain `display(df)` |

Details / a Streamlit note: `references/alternatives.md`.

## Fast path

### 1. Check once for a house style, then move on

A project or user may document table conventions (palette, currency precision) worth matching. Look **once**, cheaply — don't turn it into a project:

```bash
grep -l -iE "styler|table.?style" CLAUDE.md AGENTS.md docs/*.md 2>/dev/null
find ~/.claude/projects -maxdepth 3 -path '*/memory/reference_*.md' 2>/dev/null | grep -iE "table.?style|styler"
```

A hit → skim it and use those values. Nothing in a few seconds → take the defaults below and proceed. A good default table now beats a perfect house-style one after a five-minute hunt. (Only when the user wants to *save* a spec, or a sibling notebook's style should be mirrored, open `references/project-style-discovery.md`.)

Defaults, absent a spec:

| Setting | Default |
|---------|---------|
| Sequential cmap | `Blues` (`Blues_r` if lower = better) |
| Diverging cmap | `RdBu_r`, centered at 0 |
| Currency / percent / integer | `${:,.2f}` / `{:.1%}` / `{:,d}` |
| Headers / cells | center / right |
| Caption | descriptive; always present in findings mode |

### 2. Take the recipe for your case

**Findings table** — format numbers, shade magnitude, caption it:
```python
(df.style
   .format({'revenue': '${:,.2f}', 'customers': '{:,d}'})
   .background_gradient(cmap='Blues', subset=['revenue'])
   .set_caption('FY revenue by segment'))
```

**Delta / divergence** — center the palette at zero. This is the easy thing to get wrong: `background_gradient` with no `vmin/vmax` centers on the data's midpoint, so it paints the neutral color on the wrong cell and a value of 0 looks tinted.
```python
vmax = df.abs().max().max()
df.style.format('{:+.1%}').background_gradient(
    cmap='RdBu_r', vmin=-vmax, vmax=vmax, axis=None)
```

**Exploratory heatmap:**
```python
df.style.background_gradient(cmap='Blues', axis=None).format('{:.1%}')
# or spotlight the extremes only: .highlight_max(color='#b5e7a0')
```

Beyond these — in-cell bars, thresholds, a shared color scale across several tables, MultiIndex column groups, relabeled headers — see **Deep dives**.

### 3. Guard, render once, done

- **Empty frame first.** `df.style` on an empty DataFrame renders a headers-only table with no error — trivially easy to ship blank. Guard it:
  ```python
  if df.empty:
      print('No data')
  else:
      display(styler)
  ```
- **Render the cell once** and look at it. In an agent / Jupyter-MCP context the Styler repr won't include the HTML — dump it and read that one file: `styler.to_html('/tmp/check.html', doctype_html=True)`. One look is enough. Skip nbconvert and multi-viewport passes unless the task is specifically PDF/print export (then `references/export-and-gotchas.md`).

## Gotchas

- **`$` triggers MathJax.** In the live notebook and in `nbconvert --to html` (its template loads MathJax), a bare `$105 … $200` flips into math mode and garbles the row. Write `\$105` there. Do **not** escape in a plain `to_html(...)` file opened directly in a browser — no MathJax, so `\$` renders a literal backslash. Code fences/`` `code` `` are always safe. Full context table: `references/export-and-gotchas.md` §1.
- **`.map()` for cell CSS** in pandas ≥ 2.1 — `.applymap()` is deprecated; `.apply(axis=0|1)` for axis-aware logic.
- **Styler doesn't mutate `df`** — the chain returns a new object.
- **Captions render below the table** by default; flip with `set_table_styles([{'selector':'caption','props':[('caption-side','top')]}])`.
- **Order the chain for reading**, not correctness: `.format()` before `.background_gradient()` so the chain reads "what number → what color".

## Deep dives (open only for these)

| Need | Reference |
|------|-----------|
| More gradient / formatter / highlight patterns | `references/core-patterns.md` |
| Thresholds, comparisons, divergence detail | `references/diverging-and-thresholds.md` |
| Shared color scale across tables; MultiIndex groups | `references/multi-table-and-grouped.md` |
| Stakeholder polish (header CSS, relabel, hide index) | `references/findings-polish.md` |
| PDF/HTML export, nbconvert, `to_html` | `references/export-and-gotchas.md` |
| Saving a house-style spec; mirroring a sibling notebook | `references/project-style-discovery.md` |
| Considering not using Styler at all | `references/alternatives.md` |

## When NOT to use Styler

- Target is PowerPoint/PDF where CSS won't survive nbconvert → `great_tables`, or render to HTML and screenshot.
- Reader needs to sort/filter/search → `itables`.
- Just a structural check (`df.dtypes`, `df.head()` while debugging) → plain `display(df)`.
- Genuinely visual shape (200+ × 50+ grid) → a real heatmap chart.
- Target is Streamlit, not Jupyter → Streamlit has its own styling layer.
