# Export targets and common gotchas

Styler does most of its work as inline HTML and CSS in the rendered notebook. That's fine for live viewing — but the moment a notebook gets exported, the rules change. This file covers what survives each export path, plus the surprises that bite first-time Styler users.

## Export targets

### nbconvert HTML — `--to html`

The friendly target. Almost everything Styler produces survives:

- `background_gradient` — survives.
- `format` — survives.
- `bar` — survives (rendered as nested CSS gradients).
- `set_table_styles` / `set_properties` — survives.
- `set_caption` — survives.
- `highlight_*` — survives.
- `hide_*` — survives.
- `set_sticky` — **does not** survive in a meaningful way; sticky headers depend on Jupyter's surrounding scroll container, which the export strips.

Run:

```bash
jupyter nbconvert --to html notebook.ipynb
open notebook.html        # macOS
```

Open the result and visually confirm. A common surprise is that some CSS classes get a different specificity in the exported HTML — you may need to inline critical styles via `set_properties()` rather than relying on table-level `set_table_styles()`.

### nbconvert PDF (LaTeX path) — `--to pdf`

Most Styler CSS does **not** survive this path. nbconvert converts cell outputs to LaTeX, and HTML/CSS styling is lost in translation. What survives:

- The formatted text (numbers, currency, percent strings — these are in the cell output as text, not as CSS).
- Captions, sometimes, depending on the LaTeX template.

What is lost:
- All color (gradients, highlights, conditional fills).
- All borders and CSS-driven spacing.
- Most font-size and alignment customization.

For PDF-bound tables, the right answers are (in order of effort):
1. Render the notebook to HTML with nbconvert, open in Chrome, print to PDF. CSS is preserved.
2. Use `great_tables` instead of Styler — it has a real PDF target (`gt.save()` to `.png`/`.pdf`).
3. Take a screenshot of the styled HTML render and embed as an image. Last resort; not editable.

### Standalone HTML — `to_html()`

For sharing a single styled table outside a notebook (email attachment, ad-hoc shared link):

```python
html = df.style.format(...).background_gradient(...).to_html(table_uuid='my-table')

# Or write directly to a file
df.style.format(...).to_html('out.html')
```

Two important options:

```python
df.style.to_html(
    'out.html',
    inline_css=True,        # inlines styles into each <td>; survives email clients
    doctype_html=True,      # produces a complete <html> document, not a fragment
)
```

`inline_css=True` is the move for email — most clients strip `<style>` blocks but keep `style=` attributes on tags. Without it, email recipients see an unstyled table.

### Excel via `to_excel()`

Styler can write a styled `.xlsx`:

```python
df.style.format(...).background_gradient(...).to_excel('out.xlsx', engine='openpyxl')
```

Caveats:
- `background_gradient` translates to per-cell fill colors via openpyxl. Works but is slow on large tables.
- `bar()` does not translate well — Excel's native data bars exist but Styler doesn't emit them.
- `set_table_styles` mostly doesn't apply; Excel has its own header concept.

For Excel-first reporting, consider building with openpyxl directly or `xlsxwriter` — Styler is overkill for that target.

## Recurring gotchas

### 1. `$` triggers MathJax — escape it

Bare `$NN` in a markdown cell or HTML output puts the renderer into LaTeX math mode. Numbers come out italicized, spacing is wrong, and PDF export breaks. Write `\$105`, not `$105`. Applies to:

- Markdown cells.
- `display(HTML(...))` strings.
- `set_caption('Cost: \$1,200 per piece')`.

Inline `` `code` `` spans and triple-backtick code fences are exempt — MathJax skips them.

(If the active project's `CLAUDE.md` already documents this rule, link to that file rather than restating it here.)

### 2. `Styler` does not mutate the DataFrame

```python
df = pd.DataFrame(...)
styled = df.style.format({'revenue': '${:,.0f}'})
# df is unchanged. df['revenue'] is still the underlying float.
# styled is a separate Styler object holding the formatting rules.
```

This trips people who chain `.format()` and then try to write `df` to CSV expecting formatted strings. To get formatted text in another file, render through Styler's export methods (`to_html`, `to_excel`).

### 3. Formatter applies to display, gradient applies to data

```python
df.style.format({'rate': '{:.2%}'}).background_gradient(cmap='Blues', subset=['rate'])
```

The `format` runs on the display string; `background_gradient` runs on the underlying `float`. They can't fight — order in the chain doesn't change correctness. But the conventional reading order is "format then color," so put `.format()` first in the chain.

### 4. `subset=` is required for non-numeric columns

```python
df.style.background_gradient(cmap='Blues')   # raises if df has any string columns
df.style.background_gradient(cmap='Blues', subset=['revenue', 'count'])  # OK
```

The error message ("could not convert string to float") is unmistakable when it happens. Always pass `subset=` defensively when the table is wide and mixed-type.

### 5. `.format` chained twice merges

```python
df.style.format({'a': '${:,.0f}'}).format({'b': '{:.1%}'})
# Both columns formatted. Second call does NOT replace the first.
```

This is usually what you want, but it's a surprise if you expected reset semantics. To replace, build a single dict.

### 6. CSS in body cells vs. headers

`set_properties()` only affects body cells (`<td>`), not headers (`<th>`). For header styling, use `set_table_styles()` with selector `'th'` or `'th.col_heading'`. Mixing these up is the most common "why isn't my style applying?" issue.

### 7. Pandas version skew

| Method | Pandas ≥ 2.1 | Pandas < 2.1 |
|--------|--------------|--------------|
| Cell-level CSS | `.map()` | `.applymap()` |
| Hide index | `.hide(axis='index')` | `.hide_index()` |
| Hide columns | `.hide([cols], axis=1)` | `.hide_columns([cols])` |
| Map index labels | `.relabel_index(...)` | (added 1.5) |

If a project is pinned to an older pandas, the docs/recipes here may need the older method names. Check with `import pandas; pandas.__version__`.

### 8. Wide tables overflow

`set_table_styles` does not give the table a horizontal scrollbar by default. Wide tables (>10 columns) can overflow the cell width and clip on narrow screens or in HTML exports. Mitigations:

- Reduce per-column font size (`set_properties(**{'font-size': '90%'})`).
- Wrap headers across two lines with `<br>` via `relabel_index`.
- Move to a transposed layout if rows would be shorter than columns.
- Accept a wider HTML by adding `'overflow-x: auto'` to the surrounding `<div>` via `set_table_attributes`:

```python
df.style.set_table_attributes('style="display:inline-block; overflow-x:auto;"')
```

### 9. Styler is not picklable across pandas versions

Don't pickle a `Styler` and reload it on a different pandas version — the internal representation has changed across releases. Store the *DataFrame* and the *style spec*, regenerate the Styler when needed.

### 10. Empty DataFrames

`df.style` on an empty DataFrame returns a Styler that renders as `<table>` with no rows. No error, but nothing visible — easy to miss in a notebook. Guard with:

```python
if df.empty:
    print('No data to display')
else:
    display(df.style.format(...).background_gradient(...))
```
