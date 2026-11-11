# start-odoo-plugin

Starts your local Odoo Enterprise instance with demo data at
http://localhost:8069, using the latest code, and opens it in your browser.
Use it to check a feature or take screenshots for the documentation.

## Install

```
/plugin install start-odoo-plugin@odoo-tech-writer-team-skills
/reload-plugins
```

See the [main README](../../README.md#setup) to add the marketplace first.

## Usage

```
/start-odoo
```

Add a version to start a different one, for example `/start-odoo saas-20.1`
or `/start-odoo master`. Without one, it uses `20.0`.

To stop Odoo, ask Claude to stop it.

If another skill named `start-odoo` is also installed (for example, a copy in
`~/.claude/skills/`), the short name is ambiguous. Remove the duplicate, or
use the full name `/start-odoo-plugin:start-odoo`.

Claude will:

1. Check that the Odoo code, Python environment, and PostgreSQL are set up,
   and that the `odoo` and `enterprise` repos are on the same branch.
2. Pull the latest code for both repos.
3. Start Odoo. The first time, it creates the database (for example `odoo20`)
   with demo data. After that, it updates the database to the new code with
   `-u all`.
4. Wait until Odoo is ready, check that demo data is loaded, and open
   http://localhost:8069. Log in with `admin` / `admin`.

## Requirements

Complete the one-time setup in the
[Run Odoo locally](https://github.com/Felicious/odoo-writer-setup/blob/main/docs/local-odoo-instance.md)
guide in `odoo-writer-setup` first:

- PostgreSQL installed and running
- `odoo` and `enterprise` cloned in `~/Documents/odoo/`, on the same branch
- A Python environment at `~/Documents/odoo/.venv-odoo` with Odoo's
  requirements installed
- Linux (`xdg-open` opens the browser)

## Notes

- If a step fails, Claude reads the **Run Odoo locally** guide and gives you
  the matching fix.
- Claude never switches branches, force-resets git, runs `sudo`, or deletes
  databases. When a fix needs one of these, Claude gives you the command to
  run.
- Odoo keeps running in the background until you ask Claude to stop it. Your
  database and its data are kept between sessions.
