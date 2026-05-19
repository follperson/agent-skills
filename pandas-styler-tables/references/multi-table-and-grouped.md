# Multi-table and grouped layouts

When a report shows several tables that should be visually comparable, or when a table's columns are organized into MultiIndex groups, the basic single-table recipes aren't enough. This file covers cross-table color normalization, group dividers, and column-aware ascending/descending logic.

## 1. Cross-table color normalization

Problem: you render three tables one after another, each `.background_gradient(cmap='Blues')`. The reader perceives a top-of-scale value in table 1 as the same as a top-of-scale value in table 3, even though they're on different scales. The gradient is *lying* about comparability.

Fix: compute a shared `vmin`/`vmax` once, pass to every table.

```python
# Inputs: a list of DataFrames sharing a column we want comparable
subsets = {'east': df_east, 'west': df_west, 'central': df_central}
metric = 'revenue'

# Robust range from concatenated values — quantile clamp keeps outliers from washing out the scale
all_values = pd.concat([s[metric] for s in subsets.values()])
vmin, vmax = all_values.quantile([0.03, 0.97]).tolist()

for name, sub in subsets.items():
    display(
        sub.style
        .format({metric: '${:,.0f}'})
        .background_gradient(cmap='Blues', subset=[metric], vmin=vmin, vmax=vmax)
        .set_caption(f'Revenue — {name}')
    )
```

Notes:
- `0.03`/`0.97` quantiles instead of `min`/`max` for robustness — a single huge outlier won't flatten the rest of the scale.
- For diverging cmaps the analogue is `vmax = abs(all_values).quantile(0.97)` and pass `vmin=-vmax`.
- For multi-metric tables, compute one `(vmin, vmax)` per metric and pass them in a dict.

## 2. MultiIndex column group dividers

Tables with hierarchical columns (e.g., metric × period, segment × channel) need visual separators between groups, or the reader has to count their way through. Pandas doesn't ship a one-liner for this — here's the template.

```python
def add_vertical_group_lines(styler, level=0, width='4px', color='#444'):
    """Add a left border at each column-group boundary (where the level-N label changes).

    Use on a Styler whose columns are a MultiIndex. Returns the styler for chaining.
    """
    cols = styler.columns
    if not isinstance(cols, pd.MultiIndex):
        return styler
    labels = cols.get_level_values(level)
    boundaries = [i for i in range(1, len(labels)) if labels[i] != labels[i-1]]
    for i in boundaries:
        col = cols[i]
        styler = styler.set_properties(
            subset=pd.IndexSlice[:, [col]],
            **{'border-left': f'{width} solid {color}'},
        )
    return styler
```

Use it:

```python
(
    df_grouped.style                         # columns is a MultiIndex like ('revenue', 'Q1'), ('revenue', 'Q2'), ('cost', 'Q1'), ...
    .format('${:,.0f}')
    .background_gradient(cmap='Blues', axis=None)
    .pipe(add_vertical_group_lines, level=0)
    .set_caption('Quarterly results by metric')
)
```

`level=0` puts borders between top-level groups (`revenue` vs `cost`). `level=1` puts them between every period. Pick whichever the reader needs to scan against.

## 3. Column-aware ascending/descending cmaps

For tables where some columns mean "more is better" (revenue, ROI) and others mean "less is better" (cost, churn), use opposite cmaps so the reader sees a single visual story: *darker = better*.

```python
def style_table_generic(
    styler,
    asc_cols=None,        # "higher is better" — use Blues
    desc_cols=None,       # "lower is better"  — use Blues_r
    seq_cmap='Blues',
    format_dict=None,
    table_css=None,
    asc_pin=None,         # (vmin, vmax) shared across multiple tables — see §1
    desc_pin=None,        # (vmin, vmax) for the descending columns
):
    """Apply a consistent style across mixed-direction columns.

    asc_cols and desc_cols are lists of column names. Columns not in either list
    are left ungradiented (useful for keys, labels, IDs).

    asc_pin / desc_pin are optional (vmin, vmax) tuples — pass them when this
    helper is being called once per sub-table in a multi-table report and the
    fills need to be comparable across tables (see §1).
    """
    asc_cols = asc_cols or []
    desc_cols = desc_cols or []
    asc_kw  = dict(zip(('vmin', 'vmax'), asc_pin))  if asc_pin  else {}
    desc_kw = dict(zip(('vmin', 'vmax'), desc_pin)) if desc_pin else {}

    if format_dict:
        styler = styler.format(format_dict)

    if asc_cols:
        styler = styler.background_gradient(cmap=seq_cmap, subset=asc_cols, **asc_kw)
    if desc_cols:
        styler = styler.background_gradient(cmap=f'{seq_cmap}_r', subset=desc_cols, **desc_kw)

    if table_css:
        styler = styler.set_table_styles(table_css)

    return styler
```

Use with `.pipe()`:

```python
df.style.pipe(
    style_table_generic,
    asc_cols=['signups', 'roi'],
    desc_cols=['cost', 'churn'],
    format_dict={
        'signups': '{:,d}',
        'roi':     '{:.1%}',
        'cost':    '${:,.0f}',
        'churn':   '{:.2%}',
    },
)
```

Composed with shared scales across sub-tables (the §1 pattern, in one chain):

```python
all_rev  = pd.concat([d['revenue'] for d in subsets.values()])
all_cost = pd.concat([d['cost']    for d in subsets.values()])
rev_pin  = tuple(all_rev .quantile([0.03, 0.97]).tolist())
cost_pin = tuple(all_cost.quantile([0.03, 0.97]).tolist())

for name, sub in subsets.items():
    display(
        sub.style.pipe(
            style_table_generic,
            asc_cols=['revenue'], desc_cols=['cost'],
            format_dict={'revenue': '${:,.0f}', 'cost': '${:,.0f}'},
            asc_pin=rev_pin, desc_pin=cost_pin,
        )
        .hide(axis='index')
        .set_caption(f'Region: {name}')
    )
```

## 4. Locking in project defaults with `partial`

When you find yourself calling `style_table_generic` with the same cmap and CSS every time, bake them in:

```python
from functools import partial

style_my_tables = partial(
    style_table_generic,
    seq_cmap='Blues',
    table_css=[
        {'selector': 'th', 'props': [('text-align', 'center'), ('font-size', '110%')]},
        {'selector': 'td', 'props': [('text-align', 'right')]},
    ],
)

# Now every table just needs its asc/desc lists and formats
df.style.pipe(style_my_tables, asc_cols=['revenue'], desc_cols=['cost'])
```

If the discovered project style spec specifies `helpers_module`, prefer importing the project's own `style_table` and `pipe()` through that instead of redefining one. Pattern:

```python
from project.helpers.style import style_my_tables   # whatever the project exports
df.style.pipe(style_my_tables, asc_cols=[...], desc_cols=[...])
```

## 5. Stacking multi-table polish

For findings reports with several tables sharing a scale, group dividers, and a consistent header treatment, compose:

```python
shared_format = {'revenue': '${:,.0f}', 'cost': '${:,.0f}', 'roi': '{:.1%}'}
shared_caption_css = [{'selector': 'caption', 'props': [('caption-side', 'top'),
                                                         ('text-align', 'center'),
                                                         ('font-size', '110%')]}]

for name, sub in subsets.items():
    display(
        sub.style
        .format(shared_format)
        .background_gradient(cmap='Blues', subset=['revenue'], vmin=vmin, vmax=vmax)
        .background_gradient(cmap='Blues_r', subset=['cost'], vmin=vmin_c, vmax=vmax_c)
        .pipe(add_vertical_group_lines, level=0)        # if MultiIndex
        .set_table_styles(shared_caption_css)
        .set_caption(f'Performance — {name}')
    )
```

## 6. When the data is wrong shape

If you're reaching for cross-table normalization or MultiIndex dividers and the code keeps getting more elaborate, consider whether the data wants to be reshaped first. A single `pd.pivot_table` followed by a single styled render is often cleaner than three tables glued together with shared scales.
