# Agent Skills

A collection of reusable skills for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Distributed as a Claude Code marketplace — install via the plugin system or drop individual skills into a project's `.claude/skills/`.

## Available Skills

| Skill | Description |
|-------|-------------|
| [map-georeferencing](./map-georeferencing/) | Extract geospatial vector data from color-coded map images (PDF, PNG, TIFF, GeoTIFF). Full pipeline: preprocessing, color segmentation, polygonization, georeferencing, and export. |
| [pandas-styler-tables](./pandas-styler-tables/) | Style and format pandas DataFrames in Jupyter notebooks using `df.style` — heatmaps, currency/percent formatting, diverging palettes for deltas, conditional highlighting, polished tables for handoff. Discovers project- or user-level style specs before falling back to defaults. |
| [jupyter-plotly-slides](./jupyter-plotly-slides/) | Build interactive slide decks from Jupyter notebooks with live Plotly figures via nbconvert + reveal.js — charts stay interactive (hover, zoom, pan) in the deck. Bundles a slide-tagger, a build wrapper, and reference docs on slide anatomy and Plotly-in-reveal sizing. |

## Installation

### As a Claude Code plugin (recommended)

In any Claude Code session, add this repo as a marketplace and install the plugins you want. The marketplace is registered as **`follperson-agent-skills`** to avoid collisions with other marketplaces named `agent-skills`.

```text
/plugin marketplace add follperson/agent-skills
```

Claude Code will prompt you to confirm the marketplace before fetching it. Once it's added, install the plugins you want:

```text
/plugin install pandas-styler-tables@follperson-agent-skills
/plugin install jupyter-plotly-slides@follperson-agent-skills
/plugin install map-georeferencing@follperson-agent-skills
```

Each installed plugin appears in Claude Code's available-skills list and triggers based on its `description`. To verify:

```text
/plugin marketplace list        # confirms follperson-agent-skills is registered
/plugin                         # lists installed plugins
```

To pick up new commits later:

```text
/plugin marketplace update follperson-agent-skills
```

#### Local-path install (for development on this repo)

If you've cloned the repo and want to test changes before pushing, point the marketplace at the local checkout:

```text
/plugin marketplace add /path/to/your/clone/of/agent-skills
```

The marketplace name (`follperson-agent-skills`) is read from `.claude-plugin/marketplace.json`, so install commands use the same `@follperson-agent-skills` suffix either way.

### As a copy-in skill (no plugin system)

If you'd rather check a skill into a single project rather than install the marketplace:

```bash
git clone https://github.com/follperson/agent-skills.git
cp -r agent-skills/pandas-styler-tables /path/to/your/project/.claude/skills/
```

Claude Code auto-discovers skills under `.claude/skills/` on the next conversation.

## Repo layout

```
agent-skills/
├── .claude-plugin/
│   └── marketplace.json          # plugin manifest — defines what's installable
├── <skill-name>/
│   ├── SKILL.md                  # or skill.md — frontmatter + workflow
│   └── references/               # optional supporting docs the skill routes to
└── README.md
```

`marketplace.json` lists each top-level skill directory as its own plugin. To add a new skill: create the directory, add its entry to `marketplace.json`, and update the table above.

## Skill Format

Each skill is a directory with at minimum a `SKILL.md` (or `skill.md`) at the root, containing YAML frontmatter that Claude Code uses for discovery and triggering:

```yaml
---
name: skill-name
description: >
  When and why to use this skill — include trigger keywords, scope notes,
  and a hint of what's bundled.
---

# Skill Title

[Workflow, code templates, decision points, quality checklists...]
```

Supporting reference files live in `references/` and are routed to from the main SKILL.md (e.g., "for deeper detail on X, read `references/x.md`").

## Contributing

To add a new skill:

1. Create a directory with the skill name (kebab-case)
2. Add `SKILL.md` (or `skill.md`) with YAML frontmatter (`name`, `description`)
3. Add supporting reference files under `references/`
4. Add a `plugins[]` entry in `.claude-plugin/marketplace.json`
5. Update this README's skill table

## License

MIT
