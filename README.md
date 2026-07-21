# Odoo Technical Writer Team Skills

A Claude Code plugin marketplace maintained by the Odoo technical writing team.

## Installation

From Claude Code:

```
/plugin marketplace add your-org/odoo-tech-writer-team-skills
/plugin install get-pr-links-plugin@odoo-tech-writer-team-skills
/plugin install doc-impact-plugin@odoo-tech-writer-team-skills
/plugin install pr-to-task-plugin@odoo-tech-writer-team-skills
/reload-plugins
```

Replace `your-org` with this repository's actual GitHub org/user once it's pushed.

## Available plugins

| Plugin | Skill command | Description |
|---|---|---|
| `get-pr-links-plugin` | `/get-pr-links-plugin:get-pr-links-from-freeze-runbot` | Extracts PR links from runbot freeze HTML and writes them to the release notes Google Sheet |
| `doc-impact-plugin` | `/doc-impact-plugin:doc-impact <pr-url>` | Analyzes a GitHub PR for documentation impact and drafts a task for writers |
| `pr-to-task-plugin` | `/pr-to-task-plugin:pr-to-task <pr-url-or-number>` | Resolves GitHub PR(s) to their Odoo task URL |

See each plugin's own `README.md` under `plugins/<name>/` for details.

## Updating

Auto-update is off by default for this marketplace. To get the latest skills:

```
/plugin marketplace update odoo-tech-writer-team-skills
```

Or enable auto-update per-marketplace via `/plugin` → Marketplaces, or by adding this to a project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "odoo-tech-writer-team-skills": {
      "source": { "source": "github", "repo": "your-org/odoo-tech-writer-team-skills" },
      "autoUpdate": true
    }
  }
}
```

## Adding a new skill

1. Create `plugins/<new-plugin>/.claude-plugin/plugin.json` and `plugins/<new-plugin>/skills/<skill-name>/SKILL.md`.
2. Reference any bundled scripts with `${CLAUDE_PLUGIN_ROOT}/scripts/...` instead of hardcoded personal paths.
3. Add an entry for the plugin in `.claude-plugin/marketplace.json`.
4. Bump the plugin's `version` on every subsequent change.
5. Commit and push — team members with auto-update enabled pick it up automatically; others run `/plugin marketplace update odoo-tech-writer-team-skills`.
