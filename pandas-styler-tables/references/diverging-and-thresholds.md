# Diverging palettes and threshold highlighting

The patterns to reach for when a table is *about* direction or magnitude relative to a reference point — deltas, divergences, A-vs-B comparisons, threshold violations.

This is the highest-leverage category in this skill. A well-built divergence table answers "where do these two things disagree, and by how much?" at a glance.

## 1. Diverging gradient centered at zero

The basic move: pick a diverging cmap, pin `vmin`/`vmax` symmetric around zero. Without symmetry, a tiny negative number can render the same red as a large one, hiding magnitude asymmetry.

```python
import numpy as np

DIV_CMAP = 'RdBu_r'   # red = negative, blue = positive (reversed because BR feels right-handed)
                      # 'coolwarm' is the common alternative

delta_cols = ['delta_revenue', 'delta_cost', 'delta_margin']

vmax = float(np.abs(df[delta_cols]).max().max())
(
    df.style
    .format({c: '{:+.2f}' for c in delta_cols})    # leading +/- sign
    .background_gradient(cmap=DIV_CMAP, subset=delta_cols, vmin=-vmax, vmax=vmax)
)
```

Why pin `vmin`/`vmax` instead of letting pandas auto-scale?
- Auto-scale picks `vmin = df.min()`, `vmax = df.max()`. If your deltas are -0.02 to +1.50, zero ends up barely off-center and the palette midpoint slides — so the visual zero is not the actual zero.
- Symmetric pins make the visual midpoint align with `0`, which is what readers expect.
- For multi-table comparisons (see `multi-table-and-grouped.md`), shared `vmin`/`vmax` across tables also lets the eye compare magnitudes across them.

Common cmap choices:
- `RdBu_r` — red→white→blue (negative→zero→positive). Good general default.
- `coolwarm` — blue→white→red. Reverses the convention; use when you want "warm = good."
- `PiYG` — pink→white→green. Useful when red/blue is ambiguous in context.
- `BrBG` — brown→white→green-blue. Good for environment/sustainability framings.

## 2. The full divergence-table recipe

A typical "compare source A vs source B" table:

```python
# Inputs: df has columns ['key', 'a_value', 'b_value']
df = df.assign(
    delta_abs = lambda x: x['a_value'] - x['b_value'],
    delta_rel = lambda x: (x['a_value'] - x['b_value']) / x['b_value'],
)

cols_in_dollars = ['a_value', 'b_value', 'delta_abs']
cols_in_percent = ['delta_rel']

vmax_abs = float(np.abs(df['delta_abs']).max())
vmax_rel = float(np.abs(df['delta_rel']).max())

(
    df.style
    .format({c: '${:,.3f}' for c in cols_in_dollars})
    .format({c: '{:+.1%}' for c in cols_in_percent})
    .background_gradient(cmap='RdBu_r', subset=['delta_abs'], vmin=-vmax_abs, vmax=vmax_abs)
    .background_gradient(cmap='RdBu_r', subset=['delta_rel'], vmin=-vmax_rel, vmax=vmax_rel)
    .hide(axis='index')
    .set_caption('Source A vs. Source B — where they disagree')
)
```

The pattern is reusable for anything-vs-anything: model A vs. model B, current quarter vs. prior, observed vs. expected, source-1 vs. source-2 reconciliation.

## 3. Threshold coloring — when "diverging" isn't the right framing

For "is this above/below an action threshold?" use binary coloring via `.map()`, not a gradient. Gradients say "more is more"; threshold colors say "across the line."

```python
def threshold_paint(v, lo=-0.05, hi=0.05):
    """Tri-color: red if below lo, green if above hi, no fill if between."""
    if pd.isna(v):
        return ''
    if v < lo:
        return 'background-color: #fde0e0'   # soft red
    if v > hi:
        return 'background-color: #e0fde0'   # soft green
    return ''

df.style.map(threshold_paint, subset=['delta_rel'])
```

Variants:
- **Single threshold**: drop the `lo` arm, color only above `hi`.
- **Bands**: chain multiple `.map()` calls with non-overlapping subsets, or extend the function.
- **Combined with format**: `.format({'delta_rel': '{:+.1%}'})` before the `.map()` chain.

When to prefer threshold coloring over a diverging gradient:
- The action depends on whether the value crosses a known line, not how big the value is.
- Most values are clustered near zero with a few outliers — gradients waste color budget on the cluster; threshold coloring focuses attention on the outliers.
- The audience scans for exceptions ("show me the rows that need attention"), not for patterns.

## 4. Row-level highlighting — `.apply(axis=1)`

When *which row* is the call-out, not which cell. Common uses:

```python
# Outline the row that matches a key
def highlight_target_row(row, key='this_one'):
    style = 'border: 2px solid #1f77b4' if row.name == key else ''
    return [style] * len(row)

df.style.apply(highlight_target_row, axis=1)
```

```python
# Tint the whole row when a condition is met
def tint_breached(row, threshold=0.10):
    if row['churn_rate'] > threshold:
        return ['background-color: #fde0e0'] * len(row)
    return [''] * len(row)

df.style.apply(tint_breached, axis=1)
```

The return must be a list of CSS strings the same length as the row.

## 5. Cell-level coloring with a row-aware condition

The hard one: "color cell X red if cell Y in the same row is above threshold." `.apply(axis=1)` is the tool — return CSS only for the column(s) you want to paint:

```python
def flag_a_when_b_exceeds(row, target_col='value', condition_col='delta_rel', threshold=0.10):
    out = pd.Series('', index=row.index)
    if row[condition_col] > threshold:
        out[target_col] = 'background-color: #fde0e0'
    return out

df.style.apply(flag_a_when_b_exceeds, axis=1)
```

The trick: return a `pd.Series` aligned to `row.index`, not a bare list. Then only the cells you fill have any style.

## 6. Diverging gradient + threshold outlines

Sometimes you want *both* — gradient for magnitude, plus an outline on cells that breached a threshold. Stack them; CSS doesn't fight as long as the rules target different properties.

```python
def outline_if_breached(v, threshold=0.10):
    if pd.isna(v):
        return ''
    return 'border: 2px solid #d62728' if abs(v) > threshold else ''

vmax = float(np.abs(df['delta_rel']).max())
(
    df.style
    .format({'delta_rel': '{:+.1%}'})
    .background_gradient(cmap='RdBu_r', subset=['delta_rel'], vmin=-vmax, vmax=vmax)
    .map(outline_if_breached, subset=['delta_rel'])
)
```

`background-color` from the gradient and `border` from `.map()` apply to the same `<td>` without conflict.

## 7. Anti-patterns

- **Using a sequential cmap for a delta column.** Loses sign information; positive and negative both render as "more blue." Always use a diverging cmap for signed values around a reference point.
- **Forgetting to format the column.** A delta of `0.0345` is unreadable without `{:+.1%}` or `{:+.3f}`. Format and color together.
- **Not pinning `vmin`/`vmax` symmetrically.** Lets pandas choose, which shifts the visual zero off-center.
- **Tinting every row in a long table.** Defeats the purpose of conditional highlighting — if everything is red, nothing is red. Reserve the highlight for the 5-20% of rows that actually warrant it.
