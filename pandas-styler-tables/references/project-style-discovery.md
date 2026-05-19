# Project style discovery

Before styling a table, find out what the project (or user) already prefers. Discovery turns this skill from "applies one opinionated style" into "applies the project's style, falling back to one when there isn't one." The fallback ought to be rare — most working contexts have implicit conventions, and the skill should pick them up.

## Lookup order (stop on first hit)

### (a) Project-level style doc

Search the active repo for a committed style spec. From the current working directory:

```bash
find . -maxdepth 4 -type f \
  \( -name "styler-style.md" -o -name "tables-style.md" -o -name "table-style.md" \) \
  2>/dev/null

grep -l -E "^##+[[:space:]]+(Tables?|Styler|Table[[:space:]]+style)" \
  CLAUDE.md AGENTS.md docs/CLAUDE.md docs/AGENTS.md 2>/dev/null
```

A project style doc is the strongest signal because it's intentional and team-shared. If the project's `CLAUDE.md` or `AGENTS.md` has a `## Tables` or `## Table style` section, that wins over anything else.

### (b) User memory

Personal defaults that follow the user across all projects on this machine:

```bash
find ~/.claude/projects -maxdepth 3 -path '*/memory/reference_*.md' 2>/dev/null \
  | grep -iE "(styler|table.?style|style.?table)"
```

Matches memory entries like `reference_table_style.md`, `reference_styler_defaults.md`, etc. The user has agreed for these to function as their personal defaults.

### (c) Helper modules in active project

Some projects encode their style as code rather than a doc — a `style.py` exporting `style_table()` or `apply_house_style()`:

```bash
find . -path './.git' -prune -o -name "*style*.py" -type f -print 2>/dev/null \
  | grep -v -E "(site-packages|\.venv|\.conda|node_modules)" \
  | head
```

If you find one, read it and mirror its conventions (cmap, format strings, CSS). Note: if the helper module is importable from the active notebook, *use it* rather than duplicating its logic — `df.style.pipe(style_table)`.

### (d) Sibling notebooks

If a notebook in the same analysis directory (or a recent sibling) already uses `.style.`, mirror those choices. Search:

```bash
# From the analysis directory:
find . -maxdepth 3 -name "*.ipynb" -mtime -90 2>/dev/null \
  -exec grep -l "\.style\." {} \;
```

Then sample 2-3 styled cells from one and adopt the patterns (cmap, currency format, caption style). Announce: "Mirroring style from `<filename>`."

### (e) Ask the user — only if (a)-(d) all fail

When all four searches return nothing, ask **once**, with sensible defaults pre-selected. Then offer to save the answer so it's discoverable next time.

**Prompt template** (use the `AskUserQuestion` tool):

> **Question:** I couldn't find an existing table-style spec in this project, your memory, or sibling notebooks. Pick defaults for this skill to use:
>
> **Options:**
> - **Neutral defaults** (Recommended): Blues sequential, RdBu_r diverging (center=0), `${:,.2f}` currency, `{:.1%}` percent, center-aligned headers, right-aligned cells, descriptive caption.
> - **Greens-forward**: Same as above but Greens / Greens_r for sequential. Common in finance/ops contexts where "more green = better" reads naturally.
> - **Print-friendly grayscale**: `Greys`, no fills below mid-gray, larger fonts. For tables headed to PDF or print.
> - **Custom**: I'll ask follow-up questions about each setting.

After they answer, offer:

> **Save this for next time?**
> - **Save to user memory** (default) — personal, follows you across projects. Writes to the user's active memory dir (typically `~/.claude/projects/<sanitized-pwd>/memory/reference_table_style.md`) and appends an index line to that dir's `MEMORY.md`.
> - **Save to project** — committed to this repo. Writes to `docs/tables-style.md` or a path you specify.
> - **No** — just use these defaults for now without saving.

Default to **memory** when the user is in a personal/exploratory context, **project** when they're in a shared repo and indicate team intent.

## Style-spec schema

A style spec — whether in a project doc, memory entry, or your head — should be expressible as this YAML. Treat missing fields as falling back to skill defaults.

```yaml
sequential_cmap: <matplotlib cmap, e.g., Blues>
sequential_cmap_reversed: <e.g., Blues_r>     # for "lower=better" columns
diverging_cmap: <e.g., RdBu_r>
diverging_center: <numeric, usually 0>
currency_format:
  rates: '${:,.3f}'           # per-unit rates with several decimals
  totals: '${:,.0f}'          # whole-dollar totals
  thousands: '${:,.1f}K'      # totals scaled to K
percent_format:
  ratios: '{:.1%}'            # ROI, conversion rates
  rates: '{:.3%}'             # fine-grained probabilities (signup rates, churn)
integer_format: '{:,d}'
header_css: 'text-align:center; font-size:110%'
cell_css: 'text-align:right; font-size:100%'
caption_css: 'text-align:center; font-size:110%'
caption_side: top             # or bottom (Styler default)
helpers_module: null          # optional path to a project helper module exporting style_table()
```

Notes:
- `currency_format` and `percent_format` are nested intentionally — different precisions for different *kinds* of money/ratio. Use `rates` for per-unit values and `totals`/`ratios` for aggregates.
- `helpers_module`, when set, means "this project has a Python module that codifies the style." Prefer using it (`df.style.pipe(...)`) over hand-rolling.

## Template for a new project style doc

If a project doesn't have a style doc and the user wants to create one, copy this into `docs/tables-style.md` (or wherever fits the project's convention):

```markdown
# Table style — <project name>

This is the style spec used by the `pandas-styler-tables` skill when displaying
DataFrames in this project's notebooks. Edit values below to change behavior.

\`\`\`yaml
sequential_cmap: Blues
sequential_cmap_reversed: Blues_r
diverging_cmap: RdBu_r
diverging_center: 0
currency_format:
  rates: '${:,.3f}'
  totals: '${:,.0f}'
  thousands: '${:,.1f}K'
percent_format:
  ratios: '{:.1%}'
  rates: '{:.3%}'
integer_format: '{:,d}'
header_css: 'text-align:center; font-size:110%'
cell_css: 'text-align:right; font-size:100%'
caption_css: 'text-align:center; font-size:110%'
caption_side: top
helpers_module: null
\`\`\`

## Conventions

- (Add project-specific conventions here — e.g., "for cohort tables, lock the
  color scale at the 3rd–97th percentile of the year-to-date range")
```

(The `\`\`\`` fences inside the template are escaped for display; remove the backslashes when writing the actual file.)

## Edge cases

- **Multiple specs found.** Project doc wins over memory wins over sibling notebooks. Announce which one was chosen so the user can correct if wrong.
- **Spec is incomplete.** Use specified values; fall back to skill defaults for everything else. Don't refuse to render over a missing field.
- **Spec contradicts the request.** If the user explicitly asks for a different cmap or format in the prompt, the prompt wins for that table only; don't update the spec without being asked.
- **No active project (notebook outside a git repo or working dir).** Skip (a) and (c); rely on memory and the prompt.
