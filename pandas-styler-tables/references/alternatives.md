# Alternatives — when not to use Styler

Styler is a good fit for "this is a table I want the reader to scan with visual aids" — moderate row counts, browser display, exploratory or findings context. Outside that fit, there are better tools.

The right framing: pick the tool whose *deliverable* matches the audience's need, not the tool you already know how to use.

## Decision summary

| Situation | Use |
|-----------|-----|
| Live notebook, table is the artifact, <~100 rows, color/format helps the reader | **pandas Styler** (this skill) |
| Reader needs to sort, filter, or search the table interactively | `itables` |
| Publication-grade output for paper/exec deck/PDF with table parts (stub, spanner, footnote) | `great_tables` |
| Reader just needs to see the data, no story | plain `display(df)` |
| >100 rows AND looking for patterns | a real heatmap (Plotly `px.imshow`, seaborn) |
| Excel-first reporting | openpyxl or xlsxwriter directly |
| Streamlit dashboard | Streamlit's table layer |

## `display(df)` — plain old repr

When to pick it: the table is a step in the analysis, not a deliverable. Examples:
- `df.head()` to spot-check schema.
- `df.dtypes` to confirm types after a join.
- `df.describe()` while exploring.
- Any moment where coloring would be noise.

Styler has a non-trivial render cost (CSS strings, per-cell logic). For inspection moments, plain `display` is faster to write and faster to render.

## `great_tables` — publication-grade

`great_tables` is a separate library (`pip install great-tables`) modeled on R's `gt`. It's structured around real table parts: stub, column labels, spanner labels, body, source notes, footnotes.

When to pick it:
- Output destination is a PDF, paper, or external report.
- You need footnotes pointing at specific cells.
- You need spanner labels above column groups (a feature Styler can mimic but not name).
- You're targeting an audience that will print the result.

```python
from great_tables import GT, md

(
    GT(df)
    .tab_header(title='Q1 results', subtitle='By channel')
    .fmt_currency(columns=['revenue', 'cost'])
    .fmt_percent(columns=['roi'], decimals=1)
    .tab_source_note(source_note=md('Source: internal data warehouse'))
)
```

`great_tables` has a real PDF target (`.save('out.pdf')`) that doesn't go through nbconvert's LaTeX path, so all formatting survives.

When not to pick it: live exploratory work. The API is more verbose and the iteration cycle is slower than Styler.

## `itables` — interactive

`itables` (`pip install itables`) renders DataFrames as DataTables.net widgets — sortable, filterable, paginated, searchable.

When to pick it:
- Reader wants to interact with the data, not just look at it.
- The table is long (>100 rows) and you want pagination.
- You're sharing a notebook to read, not present.

```python
from itables import show
show(df)
```

Drop-in for `display(df)`. `itables` has limited styling compared to Styler — you trade visual treatment for interactivity. Don't try to combine them; pick one.

## Heatmap chart instead of a styled matrix

When the table is a 2D grid where all cells are the same metric (correlation matrix, period × segment counts, retention cohort grid), and there are more than ~50 rows or columns, a Styler heatmap loses to a Plotly or seaborn heatmap:

```python
import plotly.express as px
fig = px.imshow(matrix, color_continuous_scale='RdBu_r', zmin=-1, zmax=1)
fig.show()
```

Advantages:
- Hover shows the exact value without taking visual space for it.
- Zoom/pan for very large matrices.
- Better color rendering at small cell sizes than CSS gradients.

Use Styler when the cells contain *different kinds* of numbers (counts here, dollars there, percentages elsewhere). Use a heatmap when every cell is the same kind and you mostly care about color.

## Excel for the destination

If the output is `.xlsx` and the reader will open it in Excel:
- Styler's `to_excel()` works but has limitations (no `bar()`, slow on large tables).
- `openpyxl` or `xlsxwriter` directly gives you full control over Excel formats, conditional formatting rules, and native data bars.

The decision usually rests on whether the *report* lives in a notebook or in Excel. Notebook-first → Styler. Excel-first → openpyxl/xlsxwriter.

## Streamlit

Streamlit (`st.dataframe`, `st.table`) has its own styling layer. Styler objects *can* be passed to `st.dataframe`, but the result depends on Streamlit's version and not all CSS survives. For Streamlit-bound tables, use Streamlit's native style API.

For Streamlit-specific work, this user has a separate `developing-with-streamlit` skill. Use it instead of mixing concerns.

## When in doubt

A 30-second test:

1. Is the table going to be read in a Jupyter notebook? → Styler is a fine default.
2. Is the table going to be read somewhere else? → Pick the tool that natively targets that destination.
3. Does the reader need to interact with the table? → `itables` or a real dashboard tool, not Styler.
4. Is the deliverable a printed page or a slide? → `great_tables` or a screenshot, not Styler.
