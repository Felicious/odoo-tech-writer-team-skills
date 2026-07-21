# doc-impact-plugin

Analyzes a GitHub PR (odoo/odoo or odoo/enterprise) for documentation impact and drafts a task card for a technical writer.

## Usage

```
/doc-impact-plugin:doc-impact https://github.com/odoo/odoo/pull/264299
```

Copies the generated task description to the clipboard and opens the Odoo task creation page.

## Requirements

- `gh` CLI, authenticated
- `xclip` (clipboard) and `xdg-open` (opening the task page) — Linux desktop tools
- A local checkout of the documentation repo at `/home/odoo/Documents/odoo/documentation/content` (standard path for the team)
