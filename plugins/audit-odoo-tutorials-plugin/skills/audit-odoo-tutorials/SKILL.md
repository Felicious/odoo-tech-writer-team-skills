---
name: audit-odoo-tutorials
description: Audits the "Odoo Tutorials" YouTube series for a given app (e.g. MRP, Sales, Inventory, Accounting) via the docs/video search index, and outputs an ordered list of tutorial videos sorted oldest-to-newest by last-updated date, copies that list to the clipboard, and writes it to a Google Doc as a new tab (one tab per app, so one doc can hold several app audits). Phase 1 of the tutorial audit workflow; its list is the input of tutorial-audit-sheet.
---

You are auditing the official "Odoo Tutorials" YouTube video series for one app. These are the short branded how-to videos titled `<Topic> | Odoo <App>` (e.g. `Bill of Materials Basics | Odoo MRP`), each with a description starting "In this video, learn how to..." and a "**Check out more Odoo tutorials**" footer. Do not confuse these with webinars, "Odoo Quick Tips" shorts, customer-story videos, or tutorials branded for a *different* app.

**INTERACTION FLOW**

1. Determine the target app from `$ARGUMENTS` (e.g. "MRP", "manufacturing", "Sales", "Inventory"). If none is given, ask the user which app to audit. `$ARGUMENTS` may also contain a Google Doc URL: that's the doc to add the audit to (Step 6).
2. Map the app name to:
   - the doc-index `module` filter value (call `mcp__claude_ai_Content_search__list_doc_modules` if you're not sure of the exact slug — e.g. "MRP" → `manufacturing`, "Sales" → `sales`)
   - the title-branding suffix used in that app's tutorial titles — usually `Odoo <App>` (e.g. `Odoo MRP`, `Odoo Sales`), but confirm it from the first search results since it isn't always the module name verbatim.
3. Search and merge (steps below), then output the ordered list, copy it to the clipboard, and write it to a Google Doc.

---

**STEP 1 — Broad multi-angle search**

The video search tool (`mcp__claude_ai_Content_search__search_odoo_docs`, `doc_type: "video"`, `module: <slug>`) caps at 50 results per call and has no pagination, and a single query only surfaces its top-ranked matches — it will NOT return the full catalog in one call. To get full coverage, run it **5-8 times** with different phrasings that each target a different slice of that app's feature surface (e.g. for MRP: "Odoo Tutorials manufacturing", "shop floor work order", "quality control maintenance PLM", "replenishment reordering sales order", "costing valuation traceability", "engineering change order ECO", "process manufacturing order kit routing"). Use `limit: 50` each time.

For each call:
- If the result is small, it comes back inline.
- If it's large, the tool persists it to a file under the tool-results dir and gives you the path — note that path.

---

**STEP 2 — Merge, dedupe, filter**

Use the scratchpad directory for intermediate files. For each search result (inline or persisted), extract `.hits` into a JSON array file in the scratchpad.

Merge everything with `jq`, dedupe by `.url`, and filter to titles matching the app's branding suffix:

```bash
jq -s 'add | unique_by(.url) | map(select(.title | test(" \\| Odoo <SUFFIX>$")))' \
  batch1.json batch2.json ... > tutorials_all.json
```

Replace `<SUFFIX>` with the confirmed branding string (escape regex specials if needed). Watch for near-miss suffixes that should be *excluded* (e.g. `| Odoo Quality`, `| Odoo Inventory` showing up in an MRP-module search because the video crosses over) — only keep exact matches for the target app.

Sanity-check the count against `total` reported by your searches — if you're only picking up a fraction of the app's known catalog, run 2-3 more targeted queries on sub-topics you haven't covered yet before finalizing.

---

**STEP 3 — Sort and format as an ORDERED LIST (not a table)**

Sort ascending by `updated` (oldest first). Produce a numbered list, one video per line, in this format:

```
1. YYYY-MM-DD — Title — URL
2. YYYY-MM-DD — Title — URL
...
```

Get this with jq:

```bash
jq -r 'sort_by(.updated) | to_entries[] | "\(.key + 1). \(.value.updated[0:10]) — \(.value.title) — \(.value.url)"' tutorials_all.json
```

Post the list directly in the chat response — never as a table.

---

**STEP 4 — Note audit findings**

Briefly flag, as prose (not part of the copied list):
- Any topics that appear **twice** (same/near-identical title, different video ID) — these are re-recorded/refreshed tutorials.
- What was excluded (webinars, quick tips, other-app crossovers) and why, so the user can ask for those separately if wanted.
- That `updated` is the doc-index's last-updated date, used as a stand-in for publish date (not independently cross-checked against YouTube's own metadata, since the YouTube playlist page can't be scraped directly for a definitive list).

---

**STEP 5 — Copy the ordered list to the clipboard**

Write the plain numbered list (exactly what you posted in Step 3, no markdown table, no surrounding commentary) to a scratchpad file, then copy it using whichever clipboard tool is available on the platform:

```bash
command -v xclip  >/dev/null && xclip -selection clipboard -in <file>   # Linux X11
command -v wl-copy >/dev/null && wl-copy < <file>                       # Linux Wayland
command -v pbcopy  >/dev/null && pbcopy < <file>                        # macOS
```

Confirm to the user that the list has been copied.

---

**STEP 6 — Write the list to a Google Doc**

Each app goes in its own tab, so one doc can hold the audits of several apps.

- If `$ARGUMENTS` has a Google Doc URL, add a new tab to that doc.
- If not, ask the user in plain text: paste the link of an existing doc to add a tab to it, create a new doc, or skip. Wait for the answer.

Use the same list file as Step 5. `--app` is the app name from the title suffix (e.g. `MRP` for `| Odoo MRP`):

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/write_doc.py" <file> --app <App> --doc <URL>   # add a tab
python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/write_doc.py" <file> --app <App>               # new doc
```

The script names the tab after the app. If the doc already has a tab with that name, it adds the date (`MRP (2026-11-11)`). It never changes or deletes existing tabs. It prints the URL of the new tab: give it to the user.

If `gws` is missing or fails with an auth or scope error, don't retry another way. Tell the user the list is still in their clipboard, and point them to "Set up gws" in the plugin README. The doc needs the `documents` scope (`gws auth login -s docs,drive,sheets`). Run `gws auth status` to see the granted scopes.
