---
name: tutorial-audit-sheet
description: Turns a list of Odoo tutorial videos with creation dates into a Google Sheet audit (created with gws). Assigns the version from the publish-date ranges, finds duplicates (re-recorded topics), sets priority, marks videos to archive, and starts a "Tutorials to Update" tab. Copies a template sheet so dropdown chips keep the team's colors. The Reason column is filled automatically ("No newer videos", "Archive. Redirect to <link>", "Redone on line N"); anything else is left for a person. Use after audit-odoo-tutorials, or when the user pastes a dated video list and asks for an audit spreadsheet.
---

You build a video audit spreadsheet in Google Sheets from a list of tutorial videos.

## Input

The user gives a list of videos, usually the output of the `audit-odoo-tutorials` skill:

```
1. 2024-08-23 — Vendor Pricelist | Odoo Purchase — https://www.youtube.com/watch?v=MtO2XNCE-xw
```

Accept any similar format (table, CSV, pasted rows). Each video needs a date, a title and a URL. If a date or URL is missing, ask for it. Don't guess.

The user can also give the link to a Google Doc tab written by `audit-odoo-tutorials` (a URL with `?tab=t.xxx`). Read that tab's text:

```bash
gws docs documents get --params '{"documentId": "<DOC_ID>", "includeTabsContent": true}' \
  | jq -r --arg t "<TAB_ID>" '.. | objects | select(.tabProperties?.tabId == $t)
      | .documentTab.body.content[].paragraph? // empty | [.elements[].textRun.content // ""] | join("")'
```

Skip the heading line ("Odoo <App> tutorials (audited ...)") and use the numbered lines. If the link has no `tab=`, ask which tab (app) to use.

Optional: a **"What's new" video** (a YouTube URL) or a pasted transcript for a release, such as "What's new in Purchase" for Odoo 20.

## Output tab 1: "Video List"

| Col | Header | Content |
|---|---|---|
| A | Creation Date | the date from the input |
| B | Topic | the full video title |
| C | Link | the video URL |
| D | Version | set by the script from the date |
| E | Duplicates | set by the script from your `dup_group` |
| F | Priority | set by the script |
| G | Reason | set by the script (see "Reason" below) |

There are no Tags, Category, Owner or "Changed in" columns.

## Output tab 2: "Tutorials to Update"

The script builds this tab. You don't edit it.

| Row / Col | Content |
|---|---|
| Row 1 | Title `Odoo <newest version> <App> Tutorials` (e.g. "Odoo 20 Purchase Tutorials"), bold 14pt |
| Row 2 | Headers: Existing tutorials, Potential videos to write or refresh, (blank), Task link |
| A | A unique list of the videos: one entry per topic. For a duplicate group, only the newest video is listed. A title turns **dark red** (#980000) when it's also in column B. This is a conditional formatting rule, so titles the user adds to B later are colored too. |
| B | Starts with the High-priority videos from Video List. The user adds more below them. |
| C, D | Always blank. A person fills in writers and task links. |
| Key | Two blank rows under the list, column A: "Key: / Red: Replaced in v20 / Green: New in v20" (the version is the newest one in `RANGES`). "Red" is dark red and "Green" is #6AA84F. The skill never colors anything green: the user marks new videos green by hand. |

These are the only two tabs. Don't add a Comments tab, cell notes or extra rows.

## Rules

**Version.** The helper script assigns it from the creation date. Never set it by hand:

| Published | Version |
|---|---|
| before 2023-11-08 | V16 |
| 2023-11-08 to 2024-10-03 | V17 |
| 2024-10-04 to 2025-09-18 | V18 |
| 2025-09-19 to 2026-09-25 | V19 |
| 2026-09-26 and later | V20 |

To change a cutoff, edit `RANGES` at the top of `build_sheet.py`. When you add a version, also add it to the template's dropdowns (see "Template" below).

**Duplicates.** This is your job, and the rule is strict: group two videos only when their titles have **the same key words**. Never group videos because they cover the same app or area, or because they share one word.

To compare two titles:
1. Drop the ` | Odoo <App>` suffix.
2. Ignore case, word order, hyphens, "&"/"and", "w/"/"with", plurals and word forms ("Appraisal"/"Appraisals", "Engineering"/"Engineer"), and filler words ("your", "first", "the", "a", "to").
3. Treat an abbreviation and its full form as the same word ("RFQ" = "Request for Quotation").
4. Compare the key words that are left. If any key word is in only one of the titles, they are **not** duplicates.

Duplicates:
- "Purchase Basics and Your First Request for Quotation" = "Purchase and RFQ Basics" (purchase, basics, RFQ)
- "Engineering-to-Order" = "Engineer To Order"
- "Manufacturing with Backorders" = "Manufacturing Backorders"
- "Appraisals Basics" (2025) = "Appraisals Basics" (2026)

Not duplicates:
- "Employees' Appraisal" ≠ "Performance Appraisals" ≠ "Appraisals Basics": "employees", "performance" and "basics" are each in only one title.
- "Bill Control" ≠ "Paying your First Vendor": related, but different key words.

If two titles fail the rule but you still think they might teach the same thing, they are *possible duplicates*. Don't group them yet: step 2 asks the user whether to check their transcripts. Give each group a short `dup_group` id. The script fills Duplicates with the versions of the *older* videos in the group (e.g. `V17, V18` on a V19 row). It never lists newer versions or the video's own version, so the oldest video of a group has an empty Duplicates cell. Newer videos show up in Reason instead ("Redone on line N").

**Priority and archiving.** The script handles both:
- `High`: a V17-or-older video that was never redone in V18 or later. The script also writes `No newer videos` in its Reason cell.
- **Archive**: a V17-or-older video that *was* redone in V18 or later. The script strikes through every cell of its row except Reason.
- `Low`: a V18 video with no newer duplicate (no later video in its group). Reason stays blank.
- Medium is in the dropdown for the user to set by hand. Never set it yourself.

**Reason.** The script writes it, one item per line:
- `No newer videos` on High rows.
- `Archive. Redirect to <URL>` on archived rows. The URL is the newest video in the group, and it's a clickable link.
- `Redone on line N` (or `lines N, M`) on any row that has newer duplicates. N is the sheet line of each newer video (line 1 is the header).

Never write anything else in Reason, not even when a What's New transcript is given. A person fills in the rest.

## Steps

Work in the scratchpad directory. Put downloaded transcripts in their own new folder.

### 1. Parse the list
Build `audit.json` (format in the docstring of `build_sheet.py`):
- `title`: `"<App> Video Audit (<today YYYY-MM-DD>)"`.
- `app`: the app name from the title suffix, e.g. `| Odoo Purchase` gives `Purchase`. It's used in the Tutorials to Update title.
- One entry per video with `date`, `topic` (the full title), `url` and `dup_group` (`null` if it has no duplicate).

### 2. Only if there are possible duplicates
Before the preview, list each possible duplicate pair (titles and dates) with one line on why they might teach the same thing. Then ask the user in plain text whether they want you to pull the transcripts to check. Wait for the answer.
- **Yes:** download the transcripts of only those videos with the transcript commands (step 3). Read them and compare what each video teaches. Group the videos (same `dup_group`) only when they teach the same topic. In the report, give one line per pair on what you found.
- **No:** leave them ungrouped and list them as possible duplicates in the report.

Never download transcripts for possible duplicates without a yes from the user.

### 3. Only if a What's New video or transcript is given
1. Get the What's New transcript. If you have a URL, use the commands below. If it was pasted, use that text.
2. Download the transcript of every tutorial in the list the same way. You need to know what each tutorial teaches before you can judge it.
3. Compare each tutorial against the What's New content. Put your findings **in the chat report only, never in the sheet**. For each tutorial the release changes, write one or two sentences: what changed and what the tutorial shows instead. Start with how much changed: `Major:` (the main workflow changed), `Partial:` (parts are outdated) or `Minor:` (small additions). The user can use these notes to fill in Reason.

Transcript commands:
```bash
mkdir -p <scratch>/subs && cd <scratch>/subs
yt-dlp --skip-download --write-subs --write-auto-subs --sub-langs "en,en-orig" \
  --sub-format vtt -o "%(id)s.%(ext)s" --no-warnings -q -- <ID1> <ID2> ...
python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/vtt2txt.py" <scratch>/subs   # writes <ID>.txt
```
- Use `--sub-langs "en,en-orig"`, not `en.*`. The wildcard also requests translated tracks, which trigger YouTube "429 Too Many Requests" errors.
- Don't combine `--print` with `--skip-download`. It switches to simulate mode and no captions get written.
- Auto-captions garble names ("ODU", "OD doers" for Odoo; "Odoo 90" for Odoo 19). Read through those errors.

### 4. Preview, then create
```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/build_sheet.py" audit.json --dry-run
python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/build_sheet.py" audit.json
```
Check the dry run (rows to archive start with `~~`): confirm the duplicates, High rows and archive rows look right, and that the Tutorials to Update list has one entry per topic. Then run it for real. It prints the Google Sheet URL.

The real run can also print a `WARNING:` (a version used in the data is missing from the template's dropdowns, so those cells show as invalid) or a `NOTE:` (Duplicates cells with several versions need "Allow multiple selections" in the template). Pass these on to the user in the report, with the fix: edit the template's row 2 dropdowns in the Sheets UI.

The script calls `gws` (it needs the `spreadsheets` scope) and applies the team's formatting:
- Header row: bold, centered, frozen, with a filter on all columns.
- Dates: `yyyy-mm-dd` in grey. Topic and Reason: wrapped and top-aligned.
- Links: blue, 12pt, clipped.
- Dropdowns for Version, Duplicates and Priority, with colored chips copied from the template.
- High priority cells get a thin border. Rows to archive are struck through, except the Reason cell.
- No fill colors.

### Template (colored dropdowns)
The Sheets API can't set dropdown chip colors, but copying a dropdown keeps its colors. So the script doesn't create a blank sheet. It copies the template sheet `TEMPLATE_ID` ("Tutorial Audit Template (used by Claude skill, do not delete)"), deletes the copy's column D (the template's old Tags column, so the dropdowns move to D:F), then pastes the row 2 dropdowns (D2:F2) onto every row.
- Never delete the template or change its row 2 through the API. Setting a dropdown with `setDataValidation` erases its colors.
- To add a version (e.g. V21) or change a color, the user edits the row 2 dropdowns in the Sheets UI: Data > Data validation.
- If the copy fails because the template is missing, tell the user. Don't create dropdowns through the API as a fallback, since they would have no colors.

If `gws` fails with a permission or scope error:
- Run `gws auth status`. It prints JSON with a `scopes` list. Check that `https://www.googleapis.com/auth/spreadsheets` and `https://www.googleapis.com/auth/drive` are listed (`drive` is needed to copy the template).
- If `gws auth status` isn't available (older `gws` versions; check with `gws auth --help`), make a harmless call instead: `gws drive files list --params '{"pageSize": 1}'`. Exit code 2 means an auth error (credentials missing, expired or invalid).
- If a scope is missing, tell the user to sign in again with `gws auth login -s drive,sheets` (add `docs` if they also use `audit-odoo-tutorials`). Don't fall back to a local file unless the user asks.
- If `gws` isn't installed, point the user to "Set up gws" in the plugin README.

## Report

Reply with:
- The sheet URL.
- The number of videos, how many are High priority, and how many are marked to archive.
- The duplicate groups you formed. For possible duplicates: what the transcripts showed, or, if the user declined, the pairs you left ungrouped.
- Any `WARNING:` or `NOTE:` lines the script printed.
- If there was a What's New input: the per-tutorial findings from step 3 (Major first), plus a one-line note that the results come only from the transcript and weren't checked in a database.
