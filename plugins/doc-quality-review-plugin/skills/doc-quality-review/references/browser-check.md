# Browser check (opt-in)

Run this only when the user turned it on: `--browser [URL]`, or a request in their own words to
check the page in Odoo or in the UI. It follows step 6 of `AGENTS.md` in odoo/documentation.

## Before you start

1. **Get the URL from the author, in this conversation.** If `--browser` came without a URL, ask
   for it in plain text. Never guess one, and never reuse a URL from an earlier task. If they have
   no instance, mention that `/start-odoo` (start-odoo-plugin) starts one at
   `http://localhost:8069`.
2. **Use a test database only.** Ask the author to confirm it is a local or test database if the
   URL is not `localhost`. Never use a production database.
3. **Check the version:**

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/instance_info.py <URL>
   ```

   If `version_match` is false, stop the browser check and tell the author which version the
   instance runs and which one the docs branch needs.
4. **Check the apps.** Ask which apps are installed, or open the **Apps** app and filter on
   installed apps. The modules from the source pass must be installed.
5. **Pick a browser tool:** a Playwright MCP server if one is connected, otherwise the
   `claude-in-chrome` skill. If neither is available, say so and skip the browser check.
   Every label that needed it then goes on the unverified list.

## What to check

Check only what the source pass could not settle. Don't click through the whole page.

- Labels with status `not_found`, `weak`, or `case_mismatch`.
- Labels set in OWL/JS templates or changed by inherited views.
- Menu paths with status `partial` or `app_not_found`.
- Field lists where `view_checks.py order` reported a different order or an inherited view.
- Each numbered procedure on changed lines: follow the steps in order and confirm the result the
  page describes.
- Elements with `invisible=` or `groups=` conditions: confirm the page states the condition.

## Rules while checking

- Don't create or change records beyond what the scenario needs. Prefer opening forms and
  discarding over saving.
- Never change settings on an instance you weren't told is disposable. If a procedure needs a
  setting changed, ask first.
- Take a proof screenshot of each verified screen that settles a finding. Proof screenshots are
  for the PR only and don't follow the customer-facing screenshot rules
  (`agents/pr_checklist.md`).
- Record what you verified on: URL, version, apps.
