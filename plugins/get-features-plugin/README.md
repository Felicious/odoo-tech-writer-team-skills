# get-features-plugin

Retrieves all PRs from a user-specified remote branch in odoo/odoo or odoo/enterprise, and keeps a tracked, up-to-date
list of their R&D tasks along with their likely documentation impact.

## Usage

```
/get-features-plugin:get-features [REPO BRANCH] [FILTER_CSV] [--include-fw-bot] [--doc-impact keep|drop|label|skip] [--docs-repo PATH] [--out DIR] [--fresh]
```

> **Example:** `/get-features-plugin:get-features odoo/odoo saas-19.3 "~/Documents/193_release_notes.csv" --doc-impact label --docs-repo ~/Documents/odoo/documentation --out ~/Documents/OUTPUT`

The `/get-features-plugin:get-features` command can be called with or without arguments. **Without
arguments**, the skill interactively prompts the user to update an existing list (if applicable).
Alternatively, start a new list and choose the repo (`odoo/odoo` or `odoo/enterprise`), branch
(e.g., `19.0`, `saas-19.1`), as well as any optional arguments. A full list of
[arguments](#available-arguments) is provided in the subsection below.

When run on a branch **for the first time**, the skill fetches the branch's PRs, extracts their task
IDs, and builds a spreadsheet of the tasks. fw-bot forward-port PRs and PRs without a task ID are
omitted; tasks listed in `FILTER_CSV` (its `RD Task ID` column) are marked `covered`. The answers
you give are saved for next time, except `FILTER_CSV`, which is used only on runs where you pass it.

**Later runs on the same branch** update the following columns in the same spreadsheet:

- Keep the writer columns `review_status`, `assignee` and `notes`
- `change` tracks `new`, `updated`, `covered`, `reactivated` or `gone` PRs since the last run, with changed
  cells highlighted
- `Changes` sheet logs every change
- `Runs` sheet logs every run
- Previous spreadsheet and state are backed up to `history/` (keeping the last 12)

Optionally, with **scheduled runs**, the skill gives you a `cron` line that updates the list on its
own (e.g., every Monday).

### Available arguments

| Parameter | Values | Description | Saved for later runs |
|---|---|---|---|
| `REPO` | `odoo/odoo`, `odoo/enterprise` | Repository to get PRs from | Yes |
| `BRANCH` | `master`, `saas-X.Y`, `X.0` | Base branch to get PRs from | Yes |
| `FILTER_CSV` | Path to a `.csv` file | Tasks already covered, such as a release notes export. Completed tasks are marked `covered` in the list. Used only when passed; runs without it keep earlier `covered` marks | No |
| `--include-fw-bot` | | Keeps fw-bot forward-port PRs | Yes |
| `--doc-impact` | `label`, `keep`, `drop`, `skip` | Show doc impact on all tasks (`label`), hide tasks with no impact (`keep`), hide tasks with an impact (`drop`), or no scoring at all (`skip`). Hidden tasks are still tracked. | Yes |
| `--docs-repo` | Path to a folder | Local clone of `odoo/documentation`, used to find affected doc pages | Yes |
| `--out` | Path to a folder | Where tracked lists are saved; default `~/Documents/get-features` | No |
| `--fresh` | | Backs up the existing list and starts it over | No |


## Documentation impact

Optionally, each task's documentation impact is scored from its PRs' diffs (roughly a minute for 500
PRs, without model calls.) A new `doc_impact` column is added to the list with the following values:

- `confirmed`: The PR removes or renames a UI label that a docs page shows (needs a local clone of
  `odoo/documentation`); the affected pages are listed
- `likely`: The changed lines modify user-visible labels, text, fields, buttons, menus, visibility,
  reports, settings, data records (charts of accounts, taxes, states), or add a module
- `possible`: A frontend or view file changed without a specific signal, or a feature PR changed code
- `none`: Tests, translations, or backend-only fixes
- `unknown`: No usable diff

## Outputs

Each repo and branch gets its own folder under `~/Documents/get-features/` (or `--out DIR`, or the
`GET_FEATURES_HOME` environment variable), regardless of the folder Claude Code was started from:

```
~/Documents/get-features/
└── saas-19.3_odoo_odoo/
    ├── tasks.xlsx      the spreadsheet: features, Changes and Runs sheets
    ├── tasks.csv       the features sheet as CSV
    ├── history/        dated backups of the spreadsheet (last 12)
    ├── tracking.log    output of scheduled runs, if any
    └── .data/          internal: state, PR list, diffs (cached for closed PRs), scores
```

The columns of the `features` sheet and the CSV are listed below:

- `change`, `changed_on`: What changed in the latest run, and when the row last changed
- `review_status`, `assignee`, `notes`: For writers; kept between runs
- `status`: `active`, `covered` (in `FILTER_CSV`) or `gone` (no longer on the branch)
- `task_id`, `task_url`
- `task_type`: The task's strongest `change_type` across its PRs (feature > fix > technical > other)
- `pr_number`, `pr_url`
- `tag`: The PR title's tag (`IMP`, `FIX`, `REF`…), normalized
- `change_type`: `feature`, `fix`, `technical` or `other`, from the tag
- `title`, `state`, `author`, `created_at`, `first_seen`
- `modules`, `doc_impact`, `impact_reason`, `matched_labels`, `doc_pages` (when impact scoring runs)

> **Note:** Only the writer columns are kept between runs. All edits to other columns are overwritten. If the spreadsheet is open during a run, the result is saved as `tasks.updated.xlsx` and the next run writes the main file again.

## Scripts

The following are the available scripts in `scripts/`, each usable on its own (`--help`):

- `run_tracking.py`: Runs the whole pipeline from saved settings; this is what the skill and cron call
- `extract_task_ids.py`: Extracts task IDs and tags from PR descriptions; can also write a one-off spreadsheet
- `fetch_pr_files.py`: Fetches PR diffs, reusing cached diffs of closed PRs
- `score_doc_impact.py`: Scores documentation impact
- `track_changes.py`: Compares a run with the tracked list and writes the spreadsheet, CSV and state

## Requirements

- `gh` CLI, authenticated via `gh auth login`
- `uv` (runs the scripts and installs `openpyxl` on demand)
