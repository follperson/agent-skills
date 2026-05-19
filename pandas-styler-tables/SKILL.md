---
name: pandas-styler-tables
description: "Style and format pandas DataFrames in Jupyter notebooks using df.style. Use when displaying a DataFrame as the primary artifact and visual treatment helps the reader — heatmaps, currency/percent formatting, diverging palettes for deltas, conditional row/cell highlighting, polished tables for handoff. Covers both exploratory tables (gradients, highlight_max for fast pattern-finding) and stakeholder-facing findings (formatted numbers, captions, header treatment). Includes a discovery step that looks for project-specific style specs in CLAUDE.md, project docs, user memory, and sibling notebooks before falling back to defaults. Triggers: df.style, styler, format dataframe, color cells, highlight rows, table heatmap, currency table, percent table, conditional formatting, polish this table, make this table readable, show divergence between, KPI table, background_gradient, set_table_styles, applymap with CSS, highlight_max, divergent palette, center coloring at zero."
---

# Pandas Styler Tables

Style and format pandas DataFrames for Jupyter so the table itself does work the prose otherwise would — gradients to convey magnitude, diverging palettes to show direction, formatted currency/percentages so the reader doesn't have to count digits.

This skill covers two modes:

- **Exploratory** — fast pattern-finding in your own notebook. Gradients, `highlight_max`, in-cell bars. Skip polish.
- **Findings** — handoff-grade tables for stakeholders. Formatted numbers, captions, header CSS, conditional emphasis tied to the story.

The skill is **style-spec aware**: before applying defaults, it looks for a project- or user-specific style spec and adopts those settings. That way the same skill works generically across projects while respecting house conventions in projects that have them.

## Decide if Styler is the right tool

Quick decision tree:

| Situation | Use |
|-----------|-----|
| Table is the primary artifact AND <~100 rows | **Styler** |
| Reader needs to sort/filter/search interactively | `itables` |
| Publication-grade output (paper, exec deck, PDF) with table parts (stub, spanner, footnote) | `great_tables` |
| >100 rows AND looking for patterns | a heatmap chart (Plotly `px.imshow` / seaborn) |
| Structural inspection (`.head()`, `.info()`, `.describe()` quickcheck) | plain `display(df)` |

If unsure, see `references/alternatives.md`.

## Workflow

### 1. Discover the project's style spec — do this first, every time

Search in this order, stop on the first hit:

**(a) Project repo style doc** — from the current working directory:

```bash
find . -maxdepth 4 -type f \( -name "styler-style.md" -o -name "tables-style.md" -o -name "table-style.md" \) 2>/dev/null
grep -l -E "^##+[[:space:]]+(Tables?|Styler|Table[[:space:]]+style)" CLAUDE.md AGENTS.md docs/CLAUDE.md 2>/dev/null
```

**(b) User memory** — personal defaults that follow the user across projects:

```bash
find ~/.claude/projects -maxdepth 3 -path '*/memory/reference_*.md' 2>/dev/null \
  | grep -iE "(styler|table.?style|style.?table)"
```

**(c) Helper modules in active project** — sometimes a project encodes its style as Python helpers rather than a doc:

```bash
find . -path './.git' -prune -o -name "*style*.py" -type f -print 2>/dev/null | grep -v -E "(site-packages|\.venv|\.conda|node_modules)" | head
```

**(d) Sibling notebooks** — if the active analysis directory has a recently-modified `.ipynb` using `.style.`, sample its style choices and mirror them. Announce: "Mirroring style from `<filename>`."

**(e) Ask the user, once** — only if (a)-(d) all fail. Use a single multi-choice question with sensible defaults pre-selected (see `references/project-style-discovery.md` for the exact prompt template). Offer to save the answer to either user memory (default) or a committed project doc.

For full details on the spec schema and how to phrase the ask, read `references/project-style-discovery.md`.

### 2. Apply the discovered style (or defaults)

If discovery returned a spec, apply its values. If not, use these generic defaults:

| Setting | Default |
|---------|---------|
| Sequential cmap | `Blues` |
| Sequential reversed (lower=better) | `Blues_r` |
| Diverging cmap | `RdBu_r`, center=0 |
| Currency | `'${:,.2f}'` |
| Percent | `'{:.1%}'` |
| Integer | `'{:,d}'` |
| Headers CSS | `text-align:center` |
| Cells CSS | `text-align:right` |
| Caption | descriptive, `text-align:center`, always present in findings mode |

### 3. Pick the mode

- **Exploratory** — gradients freely, `highlight_max/min`, `bar()` for in-cell magnitudes. Skip captions and polish. Fast iteration matters more than presentation.
- **Findings** — `format()` everything to discovered precision, `set_caption()` with a real title, `set_table_styles()` for headers, `relabel_index()` for human-readable labels, `hide(axis='index')` when the index is structural (row numbers).

### 4. Route to a recipe

| Need | Reference |
|------|-----------|
| Heatmap, basic gradient, formatter dict, highlight extremes | `references/core-patterns.md` |
| Show a delta, comparison, divergence, threshold violation | `references/diverging-and-thresholds.md` |
| Multiple tables sharing a color scale; MultiIndex column groups | `references/multi-table-and-grouped.md` |
| Stakeholder-facing polish (captions, headers, relabeled columns) | `references/findings-polish.md` |
| PDF/HTML export, nbconvert compatibility, `to_html()` | `references/export-and-gotchas.md` |
| Considering not using Styler | `references/alternatives.md` |

### 5. Render and verify

- Always **render the cell** after styling — visually confirm before declaring done.
- **Agent / Jupyter MCP workflows**: `mcp__jupyter__execute_cell` returns the Styler repr (`<pandas.io.formats.style.Styler at 0x...>`) without the rendered HTML payload. To verify visually without a live browser, dump the styler to a file and Read it: `styler.to_html('/tmp/check.html', doctype_html=True)`. (A browser attached to the same Jupyter session still sees the rendered table either way.)
- For PDF-bound tables, also `jupyter nbconvert --to html notebook.ipynb` (HTML only, no `--execute --inplace`) and open the resulting `.html` to confirm CSS survives the export.
- For tables wider than ~8 columns, scan on a smaller viewport; `set_table_styles` overflow behavior differs at narrow widths.
- **Guard empty DataFrames before styling** — `df.style` on an empty DataFrame renders a `<table>` with no rows and no error, easy to miss. Wrap with `if df.empty: print('No data') ; else: display(df.style. …)`.

## Cross-cutting rules

- **Escape `$` only in MathJax-rendered contexts.** Bare `$NN` triggers MathJax math mode in the live notebook and in `nbconvert --to html` output (the default template loads MathJax). Write `\$105` there. Do *not* escape in plain `to_html(...)` files opened directly in a browser — there's no MathJax, and `\$` renders as a literal backslash. Code fences and inline `` `code` `` spans are always safe. See `references/export-and-gotchas.md` §1 for full context table. (If the active project's `CLAUDE.md` already documents this rule, link to it rather than restating.)
- **`Styler` does not mutate the underlying DataFrame.** `df.style.format(...)` returns a new `Styler` object; `df` is unchanged. Don't rely on this for downstream code paths.
- **Use `.map()` for cell-level CSS in pandas ≥ 2.1.** `.applymap()` is deprecated. For axis-aware logic, `.apply(axis=0|1)` is still correct.
- **Captions render below the table by default.** Flip with `set_table_styles([{'selector': 'caption', 'props': [('caption-side', 'top')]}])`.
- **Order in the method chain matters for readability, not correctness.** Formatters apply to display strings, gradients apply to underlying numerics — they can't fight each other. But put `.format()` before `.background_gradient()` so a reader scanning the chain sees "what number → what color" in that order.

## When NOT to use this skill

- The output target is a PowerPoint or PDF where Styler CSS won't survive nbconvert → use `great_tables`, or render to HTML and screenshot.
- The reader needs to sort, filter, or search the table → use `itables`.
- The table is just a structural check (e.g., `df.dtypes`, `df.head()` while debugging) — plain `display(df)` is faster and clearer.
- The data shape is genuinely visual (200+ row × 50+ col grid of correlations) → use a real heatmap chart, not a styled table.
- The target is Streamlit, not Jupyter — Streamlit has its own styling layer; this skill's CSS conventions don't translate directly.
