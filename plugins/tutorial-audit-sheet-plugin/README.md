# tutorial-audit-sheet-plugin

Turns a dated list of Odoo tutorial videos into a Google Sheet audit. The sheet
shows which tutorials to update first, which ones were re-recorded, and which
ones to archive.

This is **phase 2** of the tutorial audit workflow. Its input is the output of
[`audit-odoo-tutorials-plugin`](../audit-odoo-tutorials-plugin/README.md)
(phase 1).

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
2. Run `/tutorial-audit-sheet`. In the same session, Claude uses the list from
   step 1. In a new session, paste the list or the link to the Google Doc tab
   that phase 1 created.
3. Open the Google Sheet and use the "Tutorials to Update" tab to plan which
   tutorials to update first.

You can also skip phase 1 and paste your own list. Each video needs a date, a
title, and a URL.

## Usage

```
/tutorial-audit-sheet
```

To start from a Google Doc tab, paste its link, for example
`https://docs.google.com/document/d/<doc-id>/edit?tab=t.xxx`. Each app has its
own tab, so open the app's tab before you copy the link.

Optional: add a "What's new" video URL or transcript for a release, for example
"What's new in Purchase" for Odoo 20. Claude then compares each tutorial with
the release and tells you, in the chat, which tutorials the release changes.

Claude will:

1. Read the list and group the videos that cover the same topic (same key words
   in the title).
2. If two videos might teach the same thing but have different titles, ask you
   whether to check their transcripts.
3. Show you a preview, then create the Google Sheet:
   - **Video List**: date, topic, link, version (from the publication date),
     duplicates, priority, and reason. Videos to archive are struck through.
   - **Tutorials to Update**: one entry per topic, with the High-priority
     videos listed as videos to refresh. You fill in the writers and task links.
4. Give you the sheet URL and a summary: number of videos, High-priority
   videos, videos to archive, and duplicate groups.

### Priority rules

| Video | Priority | Reason |
|---|---|---|
| V17 or older, never redone | High | No newer videos |
| V17 or older, redone in V18 or later | Archive (struck through) | Archive. Redirect to &lt;newest video&gt; |
| V18, no newer duplicate | Low | |

Medium is never set by the skill. Set it yourself.

## Requirements

- `gws` (Google Workspace CLI), signed in with your Odoo Google account, with
  the `sheets` and `drive` scopes. See [Set up gws](#set-up-gws).
- View access to the template sheet "Tutorial Audit Template (used by Claude
  skill, do not delete)". The skill copies it so that the dropdown colors are
  kept. If the copy fails, ask the template owner to share it with you.
- `python3` and `jq`
- `yt-dlp`, only to check transcripts or compare with a "What's new" video.

## Set up gws

Both skills in the workflow use `gws`, and it runs as your own Google account:

| Skill | gws service | Used to |
|---|---|---|
| `audit-odoo-tutorials` | `docs` | Write the list to a Google Doc tab |
| `tutorial-audit-sheet` | `drive`, `sheets` | Copy the template and fill in the sheet |
| `tutorial-audit-sheet` | `docs` | Read the list from a Google Doc tab (optional) |

### Check whether gws is ready

Check which scopes you have:

```
gws auth status
```

This prints your sign-in details as JSON. Check that the `scopes` list has
these lines:

```
https://www.googleapis.com/auth/documents
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/spreadsheets
```

If `gws auth status` doesn't work, check the other subcommands with
`gws auth --help`. Older versions of `gws` don't have `status`, and the
[gws README](https://github.com/googleworkspace/cli) doesn't document it. In
that case, run a harmless command instead:

```
gws drive files list --params '{"pageSize": 1}'
```

If this returns a file, you're signed in. Exit code 2 means an auth error: your
credentials are missing, expired, or invalid.

If `gws` isn't found, or a scope is missing, set up `gws` first.

### Let Claude set it up

If you don't have `gws`, ask Claude to set it up for you. In Claude Code, type:

```
Set up the gws CLI by following the quick start at
https://github.com/googleworkspace/cli#quick-start. I need the docs, drive and
sheets scopes for my Odoo Google account.
```

Claude will follow the guide:

1. Install `gws`, for example with `npm install -g @googleworkspace/cli`
   (needs Node.js 18 or later).
2. Run `gws auth setup` once. It creates a Google Cloud project, turns on the
   APIs, and signs you in. This step needs the `gcloud` CLI. Without `gcloud`,
   Claude walks you through the manual OAuth setup in the guide.
3. Run `gws auth login -s docs,drive,sheets` to sign in with the scopes the
   skills need.
4. Run the checks above to confirm that it works.

Some steps open a browser window to sign in or need you to click in the Google
Cloud Console. Claude tells you when to do this.

> **Notes**
>
> - Choose only the services you need (`docs,drive,sheets`). The `recommended`
>   scope set has too many scopes for an app in testing mode, and sign-in fails.
> - If sign-in fails with "Access blocked", add your Google account as a test
>   user on the OAuth consent screen in the Google Cloud Console.
> - If you already use `gws` with other services, add them to the list (for
>   example `-s docs,drive,sheets,calendar`) so you keep access to them.
> - If a skill fails with a permission or scope error later, run
>   `gws auth login -s docs,drive,sheets` again.

## Configuration

These values are in `scripts/build_sheet.py`:

- `RANGES`: the publication-date ranges for each version. When a new version is
  released, add a range here.
- `TEMPLATE_ID`: the template sheet. To add a version to the dropdowns (for
  example V21) or change a color, edit row 2 of the template in the Sheets UI
  (**Data** > **Data validation**). Don't edit the template with the API: it
  removes the dropdown colors.
