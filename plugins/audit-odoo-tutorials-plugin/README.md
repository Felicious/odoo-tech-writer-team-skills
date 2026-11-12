# audit-odoo-tutorials-plugin

Lists every video in the "Odoo Tutorials" YouTube series for one app (for
example MRP, Sales, Inventory, or Accounting), sorted from oldest to newest by
publication date. It copies the list to your clipboard and writes it to a
Google Doc, in a new tab named after the app.

This is **phase 1** of the tutorial audit workflow. Its output is the input of
[`tutorial-audit-sheet-plugin`](../tutorial-audit-sheet-plugin/README.md)
(phase 2).

## Install

```
/plugin install audit-odoo-tutorials-plugin@odoo-tech-writer-team-skills
/plugin install tutorial-audit-sheet-plugin@odoo-tech-writer-team-skills
/reload-plugins
```

See the [main README](../../README.md#setup) to add the marketplace first.

## Tutorial audit workflow

| Phase | Skill | What it does | Output |
|---|---|---|---|
| 1 | `audit-odoo-tutorials` | Finds all tutorials for one app and their publication dates | A numbered list in your clipboard and in a Google Doc tab |
| 2 | `tutorial-audit-sheet` | Finds duplicates, assigns versions and priorities, and marks videos to archive | A Google Sheet with a "Video List" tab and a "Tutorials to Update" tab |

To run the full audit:

1. Run `/audit-odoo-tutorials <app>`, for example `/audit-odoo-tutorials Purchase`.
2. Check the list and the notes Claude gives you (possible re-recorded topics,
   and the videos it excluded).
3. Run `/tutorial-audit-sheet`. In the same session, Claude uses the list from
   step 1. In a new session, paste the list or the link to the Google Doc tab.
4. Open the Google Sheet and use the "Tutorials to Update" tab to plan which
   tutorials to update first.

## Usage

```
/audit-odoo-tutorials <app> [google-doc-url]
```

If you don't give an app, Claude asks for one.

Claude will:

1. Search the Odoo docs and video index several times with different queries.
   One query returns 50 results at most, so several queries are needed to find
   the full catalog.
2. Merge the results, remove duplicate URLs, and keep only the videos titled
   `<Topic> | Odoo <App>`. Webinars, Quick Tips, and tutorials branded for
   another app are excluded.
3. Show the list, sorted oldest first, in this format:

   ```
   1. 2024-08-23 — Vendor Pricelist | Odoo Purchase — https://www.youtube.com/watch?v=...
   ```

4. Point out topics that appear twice and what was excluded.
5. Copy the list to your clipboard.
6. Write the list to a Google Doc, in a new tab named after the app. If you
   didn't give a doc URL, Claude asks whether to add a tab to an existing doc,
   create a new doc, or skip this step.

### Audit several apps in one doc

Each app gets its own tab, so you can keep all your audits in one doc. Give the
same doc URL each time:

```
/audit-odoo-tutorials MRP https://docs.google.com/document/d/<doc-id>/edit
/audit-odoo-tutorials Inventory https://docs.google.com/document/d/<doc-id>/edit
```

This adds an "MRP" tab and an "Inventory" tab. If the doc already has a tab
with the same name (for example, from an earlier MRP audit), the new tab gets
the date too: "MRP (2026-11-11)". Existing tabs are never changed.

## Requirements

- The **Content search** connector (`search_odoo_docs`) enabled in Claude.
- `jq` and `python3`
- A clipboard tool: `xclip` or `wl-copy` on Linux, `pbcopy` on macOS.
- For the Google Doc: `gws` (Google Workspace CLI), signed in with your Odoo
  Google account, with the `docs` scope, and edit access to the doc. See
  [Set up gws](../tutorial-audit-sheet-plugin/README.md#set-up-gws). Without
  `gws`, the skill still works: the list is in your clipboard.

## Notes

- The date is the index's "last updated" date, used as the publication date.
  It isn't checked against YouTube.
- If the count looks low for the app, ask Claude to run more searches on the
  topics that are missing.
