# Findings polish

Patterns that turn a working table into a handoff-ready one. Use this file when the table is going to a reader who isn't you — stakeholders, exec summary, PDF export, the markdown cell that follows is the *only* place they'll see context.

The defining difference from exploratory mode: in findings, every choice should be defensible. No "I'll fix the format later," no decorative coloring, no ungrounded captions.

## 1. Captions — short, descriptive, always

```python
df.style.set_caption('Q1 signups by channel — paid vs. owned')
```

Rules:
- One short phrase, sentence case.
- Names the dimension and the metric.
- Notes the time period or scope if relevant.
- Detailed interpretation goes in the markdown cell that follows, not in the caption.

Bad: `'Results'`, `'Data'`, `'Table 3'`.
Good: `'Signups by channel — Q1'`, `'Margin drift between source A and source B'`, `'Top 20 products by volume, 2026 YTD'`.

Captions render below the table by default. Flip to top with:

```python
caption_top = [{'selector': 'caption',
                'props': [('caption-side', 'top'),
                          ('text-align', 'center'),
                          ('font-size', '110%')]}]
df.style.set_table_styles(caption_top).set_caption('...')
```

## 2. Header treatment — `set_table_styles()`

The single biggest polish lever. Centered, slightly larger, optional weight:

```python
header_css = [
    {'selector': 'th',
     'props': [('text-align', 'center'),
               ('font-size', '110%')]},
    {'selector': 'th.row_heading',
     'props': [('text-align', 'left')]},      # row labels left-aligned
    {'selector': 'th.col_heading',
     'props': [('text-align', 'center')]},
]

df.style.set_table_styles(header_css)
```

CSS selectors that work inside Styler:
- `th` — any header cell (column or row)
- `th.col_heading` — column headers only
- `th.row_heading` — row index headers only
- `th.col_heading.level0` — top level of a MultiIndex column header (substitute `level1`, etc.)
- `td` — body cells
- `caption` — the caption
- `td.row{N}` / `td.col{N}` — specific row/column body cells (zero-indexed)

## 3. Cell-wide CSS — `set_properties()`

For body styling that doesn't depend on values:

```python
df.style.set_properties(**{
    'text-align':  'right',
    'font-size':   '100%',
    'font-family': 'system-ui',
})
```

`set_properties()` accepts a `subset=` to target columns or rows. Without `subset=`, it applies to every body cell.

## 4. Per-column overrides

When most columns share styling but one needs to be different:

```python
# Make a long-text column smaller and left-aligned
small_col_css = [{
    'selector': 'td',
    'props': [('font-size', '90%'), ('text-align', 'left')],
}]

df.style.set_table_styles({'description': small_col_css}, overwrite=False)
```

`overwrite=False` is important — without it, you replace the global table_styles list with just this dict. With `overwrite=False`, the per-column styles merge in.

## 5. Multi-line column headers via `relabel_index()`

Long column names eat horizontal space. Multi-line is often clearer than abbreviation:

```python
df.style.relabel_index(
    ['Signups<br>(count)',
     'Cost<br>($/piece)',
     'ROI<br>(% of cost)'],
    axis=1,
)
```

The HTML `<br>` works because Styler renders to HTML; pandas displays it as a literal `<br>` in plain repr, but in Jupyter it's a line break.

For MultiIndex columns, pass a list of lists matching the level structure (or use `relabel_index` per level).

## 6. Hide structural columns and indices

```python
df.style.hide(axis='index')                  # hide row index entirely
df.style.hide(['_join_key', '_etl_ts'], axis=1)   # hide internal columns
df.style.hide(level=0)                       # hide top level of MultiIndex
```

For findings, almost always `hide(axis='index')` when the index is a row number (`RangeIndex`). Keep the index when it carries meaning (date, segment, key).

## 7. Number formatting precision tuned to the audience

Findings format precision should match the reader's tolerance for noise:

| Metric type | Suggested precision |
|-------------|---------------------|
| Whole-dollar totals (>$1k) | `${:,.0f}` |
| Whole-dollar totals (>$1M, optional) | `${:,.1f}M` after dividing by 1e6 |
| Per-unit rates | `${:,.2f}` to `${:,.4f}` depending on scale |
| Ratios (ROI, share) | `{:.1%}` |
| Probabilities, rates < 1% | `{:.2%}` to `{:.3%}` |
| Counts | `{:,d}` |
| Index values, year/month | leave alone or `{:.0f}` |

Whatever the spec says wins. These are defaults if the spec is silent.

## 8. Putting it together — a findings-grade chain

```python
header_css = [
    {'selector': 'th.col_heading', 'props': [('text-align', 'center'), ('font-size', '110%')]},
    {'selector': 'caption',        'props': [('caption-side', 'top'), ('text-align', 'center'), ('font-size', '110%')]},
]

(
    df.style
    .format({
        'signups': '{:,d}',
        'cost':    '${:,.0f}',
        'roi':     '{:.1%}',
    })
    .relabel_index(['Signups', 'Cost<br>(per piece)', 'ROI'], axis=1)
    .background_gradient(cmap='Blues', subset=['signups', 'roi'])
    .background_gradient(cmap='Blues_r', subset=['cost'])         # lower cost = darker
    .set_properties(**{'text-align': 'right'})
    .set_table_styles(header_css)
    .hide(axis='index')
    .set_caption('Performance by channel — Q1 2026')
)
```

## 9. The markdown cell after the table

In a findings notebook, the table almost always sits between a section header and a markdown interpretation cell. Use that layout consistently:

```
## Result: cost per signup fell 12% in Q1

<the styled table>

We saw cost per signup fall from $X to $Y, driven primarily by ... .
The largest mover was the <channel> segment, where ... .
```

Keep the caption short (it labels the table); put the *reading* in the markdown. Don't duplicate.

## 10. Things to leave out of findings tables

- Decorative coloring with no semantic load (rainbow gradients on values that don't have a magnitude story).
- Highlighting more than ~20% of cells — emphasis loses meaning past that.
- Cute formatting (emoji indicators, smileys) unless the audience has explicitly asked for it.
- Internal IDs, ETL timestamps, debug columns.
- Sparkline bars *and* gradients on the same column.
