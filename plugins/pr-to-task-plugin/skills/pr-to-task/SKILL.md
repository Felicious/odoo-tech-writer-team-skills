---
name: pr-to-task
description: Converts one or more GitHub PR links (or PR numbers) to Odoo task URLs by fetching the PR body via gh CLI and extracting the task-XXXXXXX pattern. Falls back to showing the PR body excerpt for manual lookup if no task ID is found.
---

When the user provides GitHub PR links or PR numbers, run the script at `${CLAUDE_PLUGIN_ROOT}/scripts/pr_to_task.py` via `uv run` to resolve them to Odoo task URLs.

**STEPS**

1. Collect all PR URLs or numbers from the user's message. Accept any of these formats:
   - Full URL: `https://github.com/odoo/odoo/pull/265981`
   - Short URL: `github.com/odoo/odoo/pull/265981`
   - Bare number: `265981`

2. Run the script once with all inputs as arguments:
```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/pr_to_task.py" <pr1> <pr2> ...
```

3. Display the output to the user. For each PR the script prints:
   - PR title and URL
   - Task URL if found: `https://www.odoo.com/odoo/project/19060/tasks/XXXXXXX`
   - If no task ID found: the PR body excerpt so the user can locate the task ID manually

**FALLBACK**
If the task ID is missing from the PR body, tell the user:
> "No `task-XXXXXXX` was found in this PR. Here's the body so you can find it manually — look for a line like `task-1234567` and I'll construct the URL for you."

**NOTES**
- The script accepts multiple PR inputs in one call — batch them for efficiency.
- The script requires `gh` CLI to be authenticated (`gh auth status`).
- `uv run` handles Python execution with no extra dependencies needed.
