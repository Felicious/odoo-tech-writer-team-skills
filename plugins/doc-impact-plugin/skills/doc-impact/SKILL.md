---
name: doc-impact
description: Analyzes a GitHub PR (odoo/odoo or odoo/enterprise) for documentation impact and generates a task title + description (including the linked R&D task URL) formatted for technical writers, copied to clipboard. Opens the Odoo project task creation page.
---

Given a GitHub PR URL in `$ARGUMENTS`, analyze it for documentation impact and produce a task card for a technical writer.

## Steps

### 1. Parse the PR URL

Extract the repo (e.g. `odoo/odoo`) and PR number from `$ARGUMENTS`.

### 2. Fetch PR metadata

```bash
gh pr view <PR_NUMBER> --repo <REPO> --json title,body,labels,state,files
```

Read the PR `body` first — it explains the intent in plain language. Then scan `files` to identify which modules changed.

### 3. Extract the R&D task URL

Search the PR `body` (already fetched in step 2) for a task reference, trying these patterns in order:
- `task-id-(\d+)` (e.g. `task-id-1234567`)
- `task-(\d+)` (e.g. `task-1234567` / `Task-1234567`)
- `task\s*:\s*(\d+)` (e.g. `Task: 1234567`)
- `task\s+id\s*:?\s*\[?(\d+)` (e.g. `Task ID: [1234567]`)

If a task ID is found, build the URL: `https://www.odoo.com/odoo/project/19060/tasks/<task_id>`.

If no task ID is found, omit the `R&D Task:` line entirely from the output — do not guess or leave a placeholder.

### 4. Fetch the diff — UI-relevant files only

```bash
gh pr diff <PR_NUMBER> --repo <REPO> 2>/dev/null | grep -A 60 "diff --git.*views\|diff --git.*xml\|diff --git.*res_config\|diff --git.*security"
```

Focus only on files that affect what users see or do:
- `views/*.xml` — button labels, field names, new fields, removed fields
- `res_config_settings_views.xml` — settings added or removed
- `security/*.xml` — user groups added or removed (affects feature visibility/access)
- `static/src/**/*.xml` — frontend component templates

Skip: Python models, tests, SCSS, JS unless JS reveals UI behavior not visible in templates.

### 5. Find affected documentation files

Search the doc repo at `/home/odoo/Documents/odoo/documentation/content`:

```bash
grep -r "<module_name> <key_terms_from_pr>" \
  /home/odoo/Documents/odoo/documentation/content --include="*.rst" -l
```

Use the module name and any renamed/removed features as search terms. Read the matched files (or relevant sections) to pinpoint exact lines with impact.

### 6. Generate the task output

Produce this exact structure — plain text only, no RST markup:

```
TITLE
[DOC] <module>: <what needs updating — max 70 chars>

DESCRIPTION
PR: <full PR URL>
R&D Task: <task URL, if found in step 3>
Module: <Odoo module(s)>

What changed:
<2–3 sentences from a user perspective: what was renamed, removed, or added in
the UI. No code details. Focus on what a technical writer needs to know.>

Doc files to update:

content/applications/path/to/file.rst
- Line N: <one sentence — what to change and why>
- Lines N–N: <one sentence — what to change and why, add "(screenshot needed)"
  if the UI changed visually>
[only lines with confirmed impact]

content/applications/path/to/file2.rst  (if applicable)
- ...

New content needed:  (omit this section entirely if nothing is net-new)
- <one sentence per item — what to add and where>
```

Rules:
- Omit the `R&D Task:` line entirely if no task ID was found in step 3 — never write a placeholder
- Each line item is one sentence max
- If a doc file for the feature doesn't exist yet, note it as: `path/to/file.rst (new file needed)`
- Only include sections that have actual content — omit "New content needed" if empty
- If no documentation impact is found, output: "No documentation impact detected — changes are backend/internal only."

### 7. Copy the description body to clipboard

Copy everything below (and including) the `DESCRIPTION` line to the clipboard:

```bash
xclip -selection clipboard << 'CLIP'
<description content>
CLIP
```

Then print to screen: `Copied to clipboard.`

### 8. Open the task creation page

```bash
xdg-open "https://www.odoo.com/odoo/project/3835/tasks/new"
```

---

## Usage

```
/doc-impact-plugin:doc-impact https://github.com/odoo/odoo/pull/264299
```
