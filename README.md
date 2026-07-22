# Odoo Technical Writer Team Skills

A Claude Code plugin marketplace maintained by the Odoo technical writing team.

## Setup

1. Clone the repo:

   ```
   git clone git@github.com:Felicious/odoo-tech-writer-team-skills.git
   ```

2. In Claude Code, add the clone as a local plugin marketplace (run from the directory that contains your clone, or swap in the absolute path):

   ```
   /plugin marketplace add ./odoo-tech-writer-team-skills
   ```

3. Install the plugins:

   ```
   /plugin install get-pr-links-plugin@odoo-tech-writer-team-skills
   /plugin install doc-impact-plugin@odoo-tech-writer-team-skills
   /plugin install pr-to-task-plugin@odoo-tech-writer-team-skills
   /plugin install pr-summarizer-plugin@odoo-tech-writer-team-skills
   /reload-plugins
   ```

Because the marketplace is added from your local clone, `git pull` in that directory picks up new skills without re-adding the marketplace — see [Updating](#updating).

## Available plugins

| Plugin | Skill command | Description |
|---|---|---|
| `get-pr-links-plugin` | `/get-pr-links-plugin:get-pr-links-from-freeze-runbot` | Extracts PR links from runbot freeze HTML and writes them to the release notes Google Sheet |
| `doc-impact-plugin` | `/doc-impact-plugin:doc-impact <pr-url>` | Analyzes a GitHub PR for documentation impact and drafts a task for writers |
| `pr-to-task-plugin` | `/pr-to-task-plugin:pr-to-task <pr-url-or-number>` | Resolves GitHub PR(s) to their Odoo task URL |
| `pr-summarizer-plugin` | `/pr-summarizer-plugin:pr-summarizer` | Summarizes code changes to document them in a PR description |

See each plugin's own `README.md` under `plugins/<name>/` for details.

## Updating

Since the marketplace points at your local clone, pull the latest changes and refresh the marketplace:

```
cd odoo-tech-writer-team-skills
git pull
```

```
/plugin marketplace update odoo-tech-writer-team-skills
/reload-plugins
```

You can also toggle auto-update for the marketplace via `/plugin` → Marketplaces, so a `git pull` is all you need going forward.

## Adding a new skill

1. Create `plugins/<new-plugin>/.claude-plugin/plugin.json` and `plugins/<new-plugin>/skills/<skill-name>/SKILL.md`.
2. Reference any bundled scripts with `${CLAUDE_PLUGIN_ROOT}/scripts/...` instead of hardcoded personal paths.
3. Add an entry for the plugin in `.claude-plugin/marketplace.json`.
4. Bump the plugin's `version` on every subsequent change.
5. Commit and push — team members with auto-update enabled pick it up automatically after their next `git pull`; others run `git pull` followed by `/plugin marketplace update odoo-tech-writer-team-skills`.
