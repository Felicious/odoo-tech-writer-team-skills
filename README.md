# Odoo Technical Writer Team Skills

A Claude Code plugin marketplace maintained by the Odoo technical writing team.

## Setup

### Initialize CLAUDE.md

When you run `/init` in a Claude Code session, it will scan the codebase and generate a `CLAUDE.md` summarizing the repo's structure, conventions, and build/test commands, so future Claude Code sessions have that context automatically.

#### Prerequisites

- Claude Code installed and authenticated
- A local clone of the `odoo/documentation` repository

##### Steps

1. Open a terminal in the repo root:

```
cd <path_to_documentation_repo_root>
```

2. Start Claude Code:

```
claude
```

3. Run the init command:

```
/init
```

4. Review the generated `CLAUDE.md` and edit anything inaccurate or missing before relying on it.

5. [Keep CLAUDE.md local-only](#ensure-claudemd-is-local-only).

> **Notes**
>
> - If a `CLAUDE.md` already exists in your clone, `/init` will offer to update it rather than overwrite blindly. Review the diff before accepting.
> - Re-run `/init` any time the repo structure or conventions change significantly.

#### Ensure CLAUDE.md is local-only

When using a local `CLAUDE.md` for Claude Code, you don't want it tracked, committed, or causing merge or divergence noise across branches. Ignore it via your local git config instead of the repo's `.gitignore`.

> **Important**
>
> Do not update `.gitignore` because it is a tracked file. If you add `CLAUDE.md` to it, that change lives on your branch only, so as soon as you switch branches (or someone else does), you'll see it as an untracked/diverged change. `.git/info/exclude` is local-only. It is never committed, never pushed, and works the same regardless of which branch you're on.

##### Steps

1. Make sure `CLAUDE.md` isn't already tracked by git:

```
git ls-files --error-unmatch CLAUDE.md
```

If this returns an error (did not match any files), move on to step 2.

If it succeeds, the file is tracked; run this first (to untrack it; doesn't touch your local file):

```
git rm --cached CLAUDE.md
```

2. Add `CLAUDE.md` to your local exclude file:

```
echo "CLAUDE.md" >> .git/info/exclude
```

3. Verify it's being ignored:

```
git check-ignore -v CLAUDE.md
```

You should see `.git/info/exclude:<line>:CLAUDE.md.`

`CLAUDE.md` will now stay local to your clone, untouched by branch switches, pulls, or status checks, and won't show up in `git status`.

### Plugin setup

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

### Available plugins

| Plugin | Skill command | Description |
|---|---|---|
| `get-pr-links-plugin` | `/get-pr-links-plugin:get-pr-links-from-freeze-runbot` | Extracts PR links from runbot freeze HTML and writes them to the release notes Google Sheet |
| `doc-impact-plugin` | `/doc-impact-plugin:doc-impact <pr-url>` | Analyzes a GitHub PR for documentation impact and drafts a task for writers |
| `pr-to-task-plugin` | `/pr-to-task-plugin:pr-to-task <pr-url-or-number>` | Resolves GitHub PR(s) to their Odoo task URL |
| `pr-summarizer-plugin` | `/pr-summarizer-plugin:pr-summarizer` | Summarizes code changes to document them in a PR description |

See each plugin's own `README.md` under `plugins/<name>/` for details.

### Updating

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

### Adding a new skill

1. Create `plugins/<new-plugin>/.claude-plugin/plugin.json` and `plugins/<new-plugin>/skills/<skill-name>/SKILL.md`.
2. Reference any bundled scripts with `${CLAUDE_PLUGIN_ROOT}/scripts/...` instead of hardcoded personal paths.
3. Add an entry for the plugin in `.claude-plugin/marketplace.json`.
4. Bump the plugin's `version` on every subsequent change.
5. Commit and push — team members with auto-update enabled pick it up automatically after their next `git pull`; others run `git pull` followed by `/plugin marketplace update odoo-tech-writer-team-skills`.
