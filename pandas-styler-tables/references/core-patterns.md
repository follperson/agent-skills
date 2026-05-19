# Core patterns

The recipes you'll reach for in nearly every styled table. Listed roughly in order of frequency.

All examples assume:

```python
import pandas as pd
import numpy as np
# Style spec values from the discovery step go here, or use defaults.
SEQ_CMAP = 'Blues'        # 'Greens' if the discovered spec says so
PCT_FMT  = '{:.1%}'
CUR_FMT  = '${:,.2f}'
```

## 1. Number formatting — `df.style.format()`

The single most-used method. Formats display strings without touching underlying data.

```python
# Per-column dictionary (most common)
df.style.format({
    'revenue':   '${:,.0f}',
    'cost_rate': '${:,.3f}',
    'roi':       '{:.1%}',
    'count':     '{:,d}',
})

# Global formatter for everything numeric
df.style.format(precision=2, thousands=',', na_rep='—')

# Mix: a global default plus per-column overrides
df.style.format(precision=2, na_rep='—').format({'roi': '{:.1%}'})
```

Notes:
- `na_rep` controls how NaN is rendered. Default is `'nan'`, which looks bad.
- The dict keys are column names; ones you don't list keep their default repr.
- Format strings use Python's PEP 3101 syntax (`{:fmt}`), not C-style `%`.

## 2. Sequential gradient — `df.style.background_gradient()`

Color cells by magnitude. Use `subset` to limit to numeric columns; otherwise pandas may throw on non-numeric.

```python
df.style.background_gradient(cmap=SEQ_CMAP, subset=['revenue', 'count'])
```

`axis` controls normalization:
- `axis=0` (default) — normalize column-wise. Each column has its own min/max.
- `axis=1` — normalize row-wise. Use when rows are observations and you want a within-row heatmap.
- `axis=None` — normalize across the entire subset. Use for matrices where all cells share a scale (correlations, period-by-segment counts).

```python
# Correlation matrix — single shared scale
corr = df.corr(numeric_only=True)
corr.style.background_gradient(cmap='RdBu_r', vmin=-1, vmax=1, axis=None)
```

Pin `vmin`/`vmax` whenever the natural range isn't the data range (e.g., correlations live in [-1, 1]; deltas should be symmetric around zero — see `diverging-and-thresholds.md`).

## 3. In-cell bars — `df.style.bar()`

Tiny inline bars that show magnitude without taking a column. Best for one or two columns that benefit from at-a-glance comparison.

```python
df.style.bar(subset=['signups'], color='#5fba7d')

# Signed values: bars to the right of zero in green, left in red
df.style.bar(subset=['delta'], color=['#d65f5f', '#5fba7d'], align='mid')
```

Avoid combining `bar()` with `background_gradient()` on the same column — bars overlay the gradient and the result is muddy.

## 4. Highlight extremes — `highlight_max`, `highlight_min`, `highlight_null`

Fast call-outs without computing thresholds yourself.

```python
df.style.highlight_max(subset=['roi'], color='lightgreen')
df.style.highlight_min(subset=['cost'], color='lightgreen')   # min cost is good
df.style.highlight_null(color='#ffcccc')                       # all NaN cells
```

`axis` works the same way as in `background_gradient`: `0` for column-wise, `1` for row-wise. For a matrix-wide "where is the max?" use `axis=None`.

## 5. Hide structural columns or the index — `hide()`

When the index is a row number or a column is internal:

```python
df.style.hide(axis='index')               # hide the index entirely
df.style.hide(['_internal_id'], axis=1)   # hide one or more columns
df.style.hide(level=0)                    # hide one MultiIndex level
```

For pandas < 1.4: use `hide_index()` / `hide_columns()` (deprecated in 2.x).

## 6. Caption — `set_caption()`

Every findings-mode table should have one. Captions are below the table by default; flip with `set_table_styles` (see `findings-polish.md`).

```python
df.style.set_caption('Signups and ROI by mailing — last 8 weeks')
```

Keep it short. Detail belongs in the markdown cell that follows.

## 7. Conditional CSS — `df.style.map()` (pandas ≥ 2.1) / `df.style.applymap()` (legacy)

For cell-by-cell logic that returns CSS strings:

```python
def color_high(v, threshold=0.10):
    if pd.isna(v):
        return ''
    return 'background-color: #fde0e0' if v > threshold else ''

# Pandas ≥ 2.1 — applymap was renamed map
df.style.map(color_high, subset=['churn_rate'])

# Pandas < 2.1 fallback
df.style.applymap(color_high, subset=['churn_rate'])
```

Use `.map()` going forward. For axis-aware logic (whole row or column), use `.apply()` instead:

```python
def color_row(row, key='target'):
    style = 'border: 2px solid #1f77b4' if row.name == key else ''
    return [style] * len(row)

df.style.apply(color_row, axis=1)
```

For detailed conditional patterns see `diverging-and-thresholds.md`.

## 8. Composing a full styler

A typical findings-mode chain:

```python
(
    df
    .style
    .format({
        'revenue': '${:,.0f}',
        'roi':     '{:.1%}',
    })
    .background_gradient(cmap=SEQ_CMAP, subset=['revenue'])
    .highlight_max(subset=['roi'], color='lightgreen')
    .hide(axis='index')
    .set_caption('Q1 results by channel')
)
```

Method order doesn't affect correctness — every method returns a new `Styler` and the final HTML composes them all. Order *does* affect readability: scan top-to-bottom should match the question "what number → what color → what emphasis."

## 9. Common gotchas

- **`format` chained twice merges, doesn't replace.** Calling `.format({'a': 'X'}).format({'b': 'Y'})` formats both columns.
- **`background_gradient` on non-numeric raises.** Always pass `subset=` for tables with mixed types.
- **`subset` accepts column names, index slices, or `pd.IndexSlice`.** For row-and-column subsets use `pd.IndexSlice[rows, cols]`.
- **The HTML output is the source of truth.** If a cell looks wrong, `df.style.to_html()` and read the markup; it usually clarifies which CSS rule won.
