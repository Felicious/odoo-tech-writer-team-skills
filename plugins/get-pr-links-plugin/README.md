# get-pr-links-plugin

Extracts and reorganizes GitHub Pull Request links from runbot freeze HTML, previews them as HTML, then writes Scope and GitHub PR URL to a Google Sheet.

## Usage

```
/get-pr-links-plugin:get-pr-links-from-freeze-runbot
```

Paste the runbot freeze HTML when prompted. Review the generated preview, then confirm to write the rows to the Google Sheet.

## Requirements

- `jq`
- `gws` (Google Workspace CLI) configured with access to the target spreadsheet — see [Setup](#setup-gws-for-google-sheets-access) below
- `gh` CLI, authenticated (used by the bundled `scripts/pr_to_task.py` to resolve R&D task URLs)

## Setup: `gws` for Google Sheets access

The skill shells out to `gws sheets spreadsheets values get/batchUpdate`, authenticated as *your own* Google account — there's no shared service account.

1. **Install `gws`.** Follow the install instructions for your platform in the [googleworkspace/cli](https://github.com/googleworkspace/cli) repo.
2. **Authenticate.** Run the CLI's login/auth command and sign in with your Odoo Google account (see the repo's README for the exact command — it walks through the OAuth consent flow and needs the Sheets scope). Once done, `gws sheets ...` calls run as you.
3. **Get edit access to the target spreadsheet.** The spreadsheet is set to public read (anyone with the link can view), but that alone does **not** let `gws` write to it — writes are governed by your account's actual permission on the file. Ask the sheet owner to add your Google account as an **Editor**.
4. **Verify** with a harmless read, e.g.:
   ```bash
   gws sheets spreadsheets values get \
     --params '{"spreadsheetId": "1M1903-9sDbeY7B92x2nyA-ie1oHe6a-K0GjpWbYjhXM", "range": "Sheet1!A1:A1"}'
   ```
   If that returns data instead of a permissions error, you're set to run the skill.

## Configuration

The target spreadsheet ID is hardcoded in `skills/get-pr-links/SKILL.md`. Update it there if your team points this at a different sheet.
