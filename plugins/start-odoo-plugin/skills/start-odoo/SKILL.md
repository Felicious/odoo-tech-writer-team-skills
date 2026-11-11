---
name: start-odoo
description: Starts a local Odoo Enterprise instance with demo data at http://localhost:8069. Pulls the latest code for the odoo and enterprise repos, creates the database with demo data on first run (or updates it with -u all), waits until Odoo is ready, and opens it in the browser. Use when the user asks to start, launch, run, or open local Odoo, or wants a local instance with demo data for checking features or taking screenshots. Also stops the instance when asked. Falls back to the "Run Odoo locally" guide in odoo-writer-setup if a step fails.
---

Start a local Odoo Enterprise instance with demo data and open it at http://localhost:8069. This skill runs the commands from the **Run Odoo locally** guide in the `odoo-writer-setup` repo. When a step fails, use that guide as the fallback (see **FALLBACK**).

**SETTINGS**

- Version: from `$ARGUMENTS` if given (for example `20.0`, `saas-20.1`, `master`), otherwise `20.0`.
- Workspace: `~/Documents/odoo`. Community code: `~/Documents/odoo/odoo`. Enterprise code: `~/Documents/odoo/enterprise`. Python environment: `~/Documents/odoo/.venv-odoo`.
- Database: `odoo` + the version without dots or the `saas-` prefix (`20.0` → `odoo20`, `saas-20.1` → `odoo201`, `master` → `odoomaster`).
- Port: `8069`. Login: `admin` / `admin`.
- Log file: `odoo-<database>.log` in the scratchpad directory (or `/tmp` if there is none).

**STEPS**

1. **Check the setup.** Run these checks in one command and stop at the first failure (go to **FALLBACK**, section "One-time setup"):
   - `~/Documents/odoo/odoo/odoo-bin` exists, `~/Documents/odoo/enterprise` exists, and `~/Documents/odoo/.venv-odoo/bin/python` exists.
   - `pg_isready` succeeds. If PostgreSQL isn't running, tell the user to run `sudo systemctl start postgresql` (it needs their password). Don't run sudo yourself.

2. **Check the branches.** Both repos must be on the requested version:
   ```bash
   git -C ~/Documents/odoo/odoo branch --show-current
   git -C ~/Documents/odoo/enterprise branch --show-current
   ```
   If either one is on a different branch, stop and tell the user which repo is on which branch. Don't switch branches yourself: the repos can contain the user's work. Offer to switch them, and only do it after the user agrees.

3. **Check that Odoo isn't already running.** If `ss -ltn | grep -q ':8069 '` matches, Odoo is already running. Open http://localhost:8069 and tell the user. Don't start a second copy.

4. **Download the latest code:**
   ```bash
   git -C ~/Documents/odoo/odoo pull --ff-only
   git -C ~/Documents/odoo/enterprise pull --ff-only
   ```
   - If a pull fails because the machine is offline (`Could not resolve host`), continue with the code already there and tell the user.
   - For any other failure (local changes, no tracking information, can't fast-forward), continue with the current code, and report the error and the matching fix from the guide's **Troubleshooting → `git pull` fails** section. Never run `git reset --hard`, `git checkout -f`, or `git stash` yourself: they can delete the user's work.

5. **Start Odoo.** Check whether the database exists with `psql -lqt | cut -d'|' -f1 | grep -qw <database>`, then start Odoo with `run_in_background`, writing to the log file:
   - **Database doesn't exist yet:** create it with demo data:
     ```bash
     cd ~/Documents/odoo/odoo && ../.venv-odoo/bin/python odoo-bin -d <database> --addons-path=addons,../enterprise -i web_enterprise --with-demo 2>&1 | tee <log file>
     ```
   - **Database exists:** update it to the code you just pulled:
     ```bash
     cd ~/Documents/odoo/odoo && ../.venv-odoo/bin/python odoo-bin -d <database> --addons-path=addons,../enterprise -u all 2>&1 | tee <log file>
     ```

6. **Wait until it's ready.** Run a second background command that waits until the log contains `Modules loaded.` or a failure (`Traceback`, `CRITICAL`, `ERROR`, `Address already in use`), with a time limit of about 10 minutes. Then print the matching lines. If it fails, go to **FALLBACK**.

7. **Check the demo data.** Run:
   ```bash
   psql -d <database> -tAc "select demo from ir_module_module where name = 'base'"
   ```
   - `t`: demo data is loaded.
   - `f`: the database was created without demo data. Tell the user how to load it: open http://localhost:8069/odoo/settings?debug=1, go to **Developer Tools**, and click **Load demo data**. "Activate the developer mode (with tests assets)" doesn't load demo data.

8. **Open it.** Run `xdg-open http://localhost:8069/web/login`, then tell the user:
   - the URL and the login (`admin` / `admin`),
   - the database name and branch,
   - whether demo data is loaded,
   - anything skipped or failed along the way (for example a `git pull` that failed),
   - that you can stop Odoo when they're done.

**STOPPING ODOO**

When the user asks to stop, end, or close the instance:
- If you started it in this session, stop the background task with `TaskStop`.
- Otherwise run `pkill -f odoo-bin`.
- Confirm with `ss -ltn | grep ':8069 '`: no output means it's stopped. Tell the user the database and its data are kept.

**FALLBACK**

If any step fails and the cause isn't obvious from the error, read the **Run Odoo locally** guide and follow its matching section (**One-time setup**, **Start Odoo**, **Load demo data**, or **Troubleshooting**). Look for it in this order:

1. Local file: `~/Documents/odoo/odoo-writer-setup/docs/local-odoo-instance.md`
2. From git, if the local branch doesn't have it:
   ```bash
   git -C ~/Documents/odoo/odoo-writer-setup fetch -q origin
   git -C ~/Documents/odoo/odoo-writer-setup show origin/main:docs/local-odoo-instance.md \
     || git -C ~/Documents/odoo/odoo-writer-setup show origin/docs/run-odoo-locally:docs/local-odoo-instance.md
   ```
3. On GitHub: https://github.com/Felicious/odoo-writer-setup/blob/main/docs/local-odoo-instance.md (until PR #9 is merged: https://github.com/Felicious/odoo-writer-setup/blob/docs/run-odoo-locally/docs/local-odoo-instance.md)

Then tell the user what failed, quote the exact error line from the log, and give the fix from the guide. Steps that need `sudo` or that delete data (`dropdb`, `git reset --hard`) are for the user to run: give them the command and don't run it yourself.

If the guide doesn't cover the error, show the last 30 lines of the log file and say so.
