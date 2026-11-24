# doc-quality-review-plugin

Reviews Odoo documentation `.rst` files for **accuracy** and **style**, and returns a report with
numbered findings, evidence, and proposed fixes. Nothing is edited until you pick the findings to
apply.

- **Accuracy:** every `:guilabel:`, `:menuselection:`, setting, option list, `:ref:`, and `:doc:`
  is checked against your local `odoo/odoo` and `odoo/enterprise` checkouts. A reviewer subagent
  then reads the source to confirm behavior claims (defaults, automation, access rights, module
  installs) and compares the page with other pages about the same feature.
- **Style:** each file gets the rules for its scope from `agents/docs_ownership.md`: the US rules
  (`agents/style_rules.md` on top of the published guidelines) or the Not US rules (published
  guidelines only). An editor subagent reviews against them, plus judgment checks from
  *Developing Quality Technical Information* (Hargis et al.).
- **Automated checks:** the CI lint, the `make review` line checks, Vale (with results that
  contradict the file's scope filtered out), and optionally the `make fast` build.
- **Browser check (opt-in):** with `--browser`, follows the documented steps in a running Odoo
  instance on the same version, as step 6 of `AGENTS.md` requires.

The review follows the agent workflow in odoo/documentation's `AGENTS.md`: it stays on the files
you name, reads the parent page for context, proposes before editing, and lists anything it
couldn't verify as an open question for the PR.

## Usage

```
/doc-quality-review-plugin:doc-quality-review content/applications/hr/attendances.rst
/doc-quality-review-plugin:doc-quality-review content/applications/hr/attendances/ --browser http://localhost:8069
/doc-quality-review-plugin:doc-quality-review --branch
```

Or ask in your own words: "review attendances.rst for accuracy", "fact-check this page against the
code", "QA the docs I changed on this branch".

| Option | Effect |
|---|---|
| files or folders | Review only these. |
| `--branch` | Review the `.rst` files changed on the current branch. Also runs the build. |
| `--browser [URL]` | Also verify in a running Odoo instance. Asks for the URL if you don't give one. Off by default. |
| `--build` | Also run `make fast` and report warnings for the reviewed files. |

## Requirements

- Python 3 (standard library only).
- `odoo/documentation` checkout, with its `.venv` set up (`pip install -r requirements.txt`) for
  the lint and build checks.
- `odoo/odoo` and `odoo/enterprise` checkouts **on the same version as the docs branch**, next to
  the docs repo (`odoo-src` or `odoo`, and `enterprise`), or set `ODOO_SRC` / `ODOO_ENTERPRISE`.
- `vale` and `odoo-vale-linter` (installed by `odoo-writer-setup`). Set `VALE_CONFIG` if the
  linter isn't next to the docs repo.
- `gh`, logged in, while odoo/documentation#21055 is not merged: the rule files (`AGENTS.md`,
  `agents/*.md`) are then fetched from the PR branch, and the report says so.
- For `--browser`: a running test instance (`/start-odoo` can start one) and a browser tool
  (Playwright MCP or Claude in Chrome).

## Scripts

All in `scripts/`, each printing JSON. They can also be run on their own.

| Script | Does |
|---|---|
| `get_rules.py` | Finds `AGENTS.md` and `agents/*.md`: local checkout, then the base branch on GitHub, then PR #21055 |
| `scope_for_path.py` | US / Not US / Undecided for each file, from `agents/docs_ownership.md` |
| `extract_refs.py` | Labels, menu paths, links, icons, field lists, images, meta block, and changed lines of one file |
| `verify_ui_refs.py` | Checks labels, menu paths, and links against the source and the docs |
| `view_checks.py` | `settings`: settings the docs never mention. `order`: field and option list order vs. the view or `selection=` |
| `run_checks.py` | Lint, line review, scope-filtered Vale, and optional build |
| `instance_info.py` | Version of an Odoo instance, compared with the docs branch |

## Tests

```
python3 plugins/doc-quality-review-plugin/tests/test_scripts.py
```

The tests that need the docs or source checkouts are skipped when those aren't found.

## Notes

- When `agents/style_rules.md` changes an Override, update the Vale filter in
  `scripts/run_checks.py` and `skills/doc-quality-review/references/vale-scope-filter.md`.
- The ownership parser is a heuristic over a prose file. Every result shows the rule line it
  matched, and the tests pin the expected scope of key paths.
