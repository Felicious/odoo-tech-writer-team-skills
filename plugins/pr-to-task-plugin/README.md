# pr-to-task-plugin

Converts GitHub PR links or numbers to Odoo task URLs.

## Usage

```
/pr-to-task-plugin:pr-to-task https://github.com/odoo/odoo/pull/265981
```

Accepts full URLs, short URLs, or bare PR numbers, and multiple PRs in one call.

## Requirements

- `gh` CLI, authenticated (`gh auth status`)
- `uv` (used to run the bundled `scripts/pr_to_task.py` with no separate install step)
