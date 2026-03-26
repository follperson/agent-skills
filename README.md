# Agent Skills

A collection of reusable skills for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Each skill is a self-contained directory that can be copied into your project's `.claude/skills/` folder.

## Available Skills

| Skill | Description |
|-------|-------------|
| [map-georeferencing](./map-georeferencing/) | Extract geospatial vector data from color-coded map images (PDF, PNG, TIFF, GeoTIFF). Full pipeline: preprocessing, color segmentation, polygonization, georeferencing, and export. |

## Installation

Copy a skill directory into your project's `.claude/skills/` folder:

```bash
# Clone the repo
git clone https://github.com/follperson/agent-skills.git

# Copy a skill into your project
cp -r agent-skills/map-georeferencing /path/to/your/project/.claude/skills/
```

The skill will be automatically discovered by Claude Code on the next conversation.

## Skill Format

Each skill follows the Claude Code skill convention:

```
skill-name/
├── skill.md              # Main skill definition (YAML frontmatter + Markdown)
└── [supporting-files].md # Optional reference docs, code templates, guides
```

The `skill.md` file contains YAML frontmatter with `name` and `description` fields that Claude Code uses for discovery and triggering:

```yaml
---
name: skill-name
description: >
  When and why to use this skill...
---

# Skill Title
[Workflow, code templates, decision points, quality checklists...]
```

Supporting files are referenced from `skill.md` using `@filename.md` syntax.

## Contributing

To add a new skill:

1. Create a directory with the skill name (kebab-case)
2. Add a `skill.md` with YAML frontmatter (`name`, `description`)
3. Add any supporting reference files
4. Update this README's skill table

## License

MIT
