---
name: get-features
description: Retrieves all PRs from a user-specified remote branch in odoo/odoo or odoo/enterprise and keeps a tracked list of their R&D tasks, with documentation impact, up to date across runs. Run without arguments to pick an existing list or start a new one interactively.
argument-hint: "[REPO BRANCH] [FILTER_CSV] [--include-fw-bot] [--doc-impact keep|drop|label|skip] [--docs-repo PATH] [--out DIR] [--fresh]"
---

## Prerequisites

Ensure that `gh` CLI is installed and authenticated with `gh auth login`, and that `uv` is installed.

## How it works

The `${CLAUDE_PLUGIN_ROOT}/scripts/run_tracking.py` script runs all of the following steps for a specified repo and branch:

1. Fetch the PRs from the repo and branch.
2. Extract the tasks.
3. Score documentation impact (if specified).
4. Update the tracked list (a state file + a spreadsheet keeping track of writers' notes and what changed since the last run).

The first run saves its settings in the state file, so later runs (or a cron job) need no questions.

Each tracked list is stored in its own folder: LIST_DIR = `<OUT>/<BRANCH>_<REPO_SLUG>/`, where:

- `<OUT>` is `--out`, else `$GET_FEATURES_HOME`. In all other cases, default to `~/Documents/get-features`
- `<REPO_SLUG>` replaces `/` with `_`

The LIST_DIR folder contains the following files and directories:

| Path in LIST_DIR | Contents |
|---|---|
| `tasks.xlsx` | The spreadsheet the user opens |
| `tasks.csv` | The same list as CSV |
| `history/` | Dated backups of the spreadsheet (last 12) |
| `tracking.log` | Output of scheduled runs, if any |
| `.data/` | State file (`state.json`), PR list, diffs, scores, state backups. Internal |

> **Note:** The files in `.data/` hold every PR body and diff. Never read them into context, except as shown below.

## Steps

### 1. Parse arguments and discover options (no questions yet).

Parse `$ARGUMENTS` as `[REPO BRANCH] [FILTER_CSV] [--include-fw-bot] [--doc-impact MODE] [--docs-repo PATH] [--out DIR] [--fresh]`.

> **Note:** Everything is optional. Whatever is missing is asked in step 2.

The arguments are defined as follows:

- REPO: `odoo/odoo` or `odoo/enterprise`.
- BRANCH: The remote base branch, e.g. `master`, `19.0`, `saas-19.3`.
- FILTER_CSV: A spreadsheet of tasks already covered, e.g. a release notes export (any argument ending in
  `.csv`). Its tasks are kept in the list but marked `covered`. Used only on the run where it's passed:
  it's never saved, never asked for and never looked for. Without it, tasks keep the `covered` marks that
  earlier runs set.
- `--include-fw-bot`: Keep fw-bot forward-port PRs. Excluded by default.
- `--doc-impact MODE`: `label` (score and show everything), `keep` (hide tasks scored `none`), `drop` (hide
  tasks with an impact) or `skip` (don't score). Hidden tasks are still tracked.
- `--docs-repo PATH`: A local clone of `odoo/documentation`, for finding affected doc pages.
- `--out DIR`: Where tracked lists live, instead of `$GET_FEATURES_HOME` or `~/Documents/get-features`.
- `--fresh`: Back up an existing list and start it over.

Then, in step 2, run one Bash call that collects additional information, leaving out any parts already answered.

```bash
gh auth status 2>&1 | head -2
OUT="<OUT>" # OUT is `--out`, else `$GET_FEATURES_HOME`, else `~/Documents/get-features`:
# Tracked lists, most recently run first: repo, branch, last run.
for s in "$OUT"/*/.data/state.json; do
  [ -f "$s" ] && jq -r '[.settings.repo, .settings.branch, (.runs[0].date // "never")] | @tsv' "$s"
done | sort -t$'\t' -k3 -r
# Only if BRANCH is missing: the newest release branches (use odoo/odoo if REPO is missing).
gh api "repos/<REPO>/branches?per_page=100" --paginate --jq '.[].name' 2>/dev/null \
  | grep -E '^(saas-[0-9]+\.[0-9]+|[0-9]+\.0)$' | sort -Vr | head -3
# Only if --docs-repo wasn't given: a local clone of odoo/documentation.
for d in $(find ~ -maxdepth 4 -type d -name documentation -not -path '*/node_modules/*' 2>/dev/null); do
  git -C "$d" remote get-url origin 2>/dev/null | grep -q 'odoo/documentation' && echo "DOCS_REPO=$d" && break
done
```

Keep in mind the following:

- If FILTER_CSV was given, also print its header row with `head -1`.
- The list for REPO and BRANCH exists if `<OUT>/<BRANCH>_<REPO_SLUG>/.data/state.json` does. Never read state files beyond the `jq` above.

### 2. Ask what's missing in at most two rounds.

Each round is one `AskUserQuestion` call. Skip a round when it has nothing to ask. Every question has an
automatic "Other" for typing, so offer discovered values as options and let "Other" cover the rest.

**Round 1: which list.** Only if REPO or BRANCH is missing and at least one tracked list exists:

- **List**: Up to 3 tracked lists, most recent first, labeled `<BRANCH> · <REPO>` with "last run <date>" as
  the description, plus "Start a new list". "Other" takes an older list (e.g. `saas-19.2_odoo_odoo`) or
  `<REPO> <BRANCH>`.

Picking an existing list sets REPO and BRANCH, skips round 2 and updates the list (step 3).

**Round 2: a new list.** Only if the chosen list doesn't exist yet. Prompt for the following:

- **Repo** (if missing): `odoo/odoo`, `odoo/enterprise`.
- **Branch** (if missing): The release branches found in step 1, newest first, and `master`. If none were
  found, offer only `master` and let "Other" cover the rest.
- **Documentation impact** (if `--doc-impact` wasn't given): "Label only (Recommended)", "Hide tasks with no impact", "Skip". Mention that it adds about a minute.

Keep in mind the following:

- Don't ask about the docs clone: use `--docs-repo`, else the one found in step 1. Otherwise, run without the docs check (nothing gets scored `confirmed`). Mention which in the report.
- An existing list is always updated with its saved settings without prompting anything. Any arguments specified on the command line (`--doc-impact`, `--docs-repo`…) override the saved settings and preserves them for next time.
- Never ask for a FILTER_CSV or suggest one. Use it only if the user passed a path, and pass `--filter-column "<NAME>"` if its task column isn't `RD Task ID`.
- Don't offer a "closed PRs" filter: Odoo merges PRs through its own bot, so GitHub reports merged PRs as `closed` with an empty `merged_at`.

### 3. Run the pipeline.

Run the pipeline with `run_in_background: true` and wait for the notification.

First run:

```bash
uv run --quiet "${CLAUDE_PLUGIN_ROOT}/scripts/run_tracking.py" --repo <REPO> --branch <BRANCH> \
  --impact <MODE> [--filter-csv <FILTER_CSV> [--filter-column <NAME>]] [--docs-repo <DOCS_REPO>] \
  [--include-fw-bot] [--out <DIR>]
```

For an existing list, run the same command with only `--repo` and `--branch` (and `--out` if used), applying any saved settings. Add `--filter-csv <PATH>` only if the user passed a FILTER_CSV, `--fresh` to start over, and any other argument the user passed.

The script prints progress to stderr. Read only its last stdout line, which is a JSON summary.

### 4. Report.

From the summary, tell the user the following:

- The full path of the spreadsheet (`xlsx`), and its folder (`folder`).
- On a first run (`first_run: true`), how many tasks are tracked (`new_tasks`), how many are active
  (`tasks_active`), and how many new tasks have a `likely` or `confirmed` impact.
- On later runs, what changed since `previous_run`: `new_tasks`, `new_prs_on_known_tasks`, `updated_tasks`,
  `covered_tasks`, `reactivated_tasks` and `gone_rows`, plus the `highlights` (impact and type changes).
- The `note`, if any. "spreadsheet was open" means the result is in `tasks.updated.xlsx` and the user should close the spreadsheet; the next run writes the main file again. "scorer updated" means impact columns were refreshed for new scoring rules without logging each PR as a change.
- Which docs ref was checked (`docs_ref`).

Then, explain the spreadsheet in two sentences, mentioning: filter `change` to see this run's changes, and the `Changes` and `Runs` sheets hold the history. Only `review_status`, `assignee` and `notes` are kept between runs, while edits to other columns are overwritten.

Mention that the impact levels come from pattern matching, not from reading the PRs. Suggest `/doc-impact-plugin:doc-impact <PR URL>` for an in-depth look at specific PRs.

Finally, offer to open the spreadsheet. If the user accepts, run `xdg-open <xlsx>` (`open` on macOS).

### 5. Offer a scheduled run (first run only).

Offer this `crontab -e` line to update the list every Monday at 08:00 without Claude:

```
0 8 * * 1  PATH=<UV_DIR>:/usr/bin:/bin uv run --quiet <ABSOLUTE_PLUGIN_ROOT>/scripts/run_tracking.py --repo <REPO> --branch <BRANCH> [--out <DIR>] >> <LIST_DIR>/tracking.log 2>&1
```

Fill in absolute paths (`<UV_DIR>` from `dirname $(command -v uv)`). Mention that the plugin path changes
when the plugin is updated, so the line may need refreshing then, and that runs while the spreadsheet is
open save to `tasks.updated.xlsx`. If the user set `GET_FEATURES_HOME`, pass `--out` in the cron line,
since cron doesn't load the shell profile.

## Reference

**Spreadsheet** (`features` sheet): `change`, `changed_on`, `review_status`, `assignee`, `notes`, `status`,
`task_id`, `task_url`, `task_type`, `pr_number`, `pr_url`, `tag`, `change_type`, `title`, `state`, `author`,
`created_at`, `first_seen`, then `modules`, `doc_impact`, `impact_reason`, `matched_labels`, `doc_pages`.
Rows changed in this run come first; changed cells are highlighted. The `Changes` sheet logs every change
(newest first) and the `Runs` sheet every run.

- `change`: `new`, `updated` (state, tag, type or impact changed), `covered` (now in the filter CSV),
  `reactivated` (active again) or `gone` (no longer on the branch); empty if unchanged this run.
- `status`: `active`, `covered` or `gone`.
- `tag`: the PR title's tag (`IMP`, `FIX`, `REF`…). Variants are normalized (`[IMPR]` → `IMP`, `[NEW]` →
  `ADD`, `[IMP/FIX]` → `IMP`) and markers like `[WIP]`, `[FW]` or `[18.0]` are skipped. `OTHER` if the
  bracket holds no known tag, empty if there's none.
- `change_type`: `feature` (IMP, ADD, REM, MOV), `fix` (FIX, REV, SEC), `technical` (REF, PERF, CLN, LINT,
  I18N, MERGE, CLA, REL, POC) or `other`. `task_type` is the task's strongest across its PRs.

**Impact levels**, strongest first. A task takes the strongest level among its PRs:

- `confirmed`: the PR removes or renames a UI label that the docs show as `:guilabel:` or
  `:menuselection:`. `matched_labels` and `doc_pages` say which and where. One-word labels only count on
  pages of the PR's own app; labels shown on more than 15 pages are too generic to count; a country page
  only counts for PRs touching that country's `l10n_<code>` modules.
- `likely`: the changed lines touch something users see: labels and UI text, fields, selection options,
  buttons, menus, filters, visibility, report content, settings, data records, or a new module.
- `possible`: a frontend or view file changed without a specific signal, or an `[IMP]`/`[ADD]`/`[REM]`/`[MOV]`
  PR changed code.
- `none`: only tests and translations, or backend code in a fix, perf or refactor PR.
- `unknown`: no usable diff (`impact_reason` says why).

**Scripts** in `${CLAUDE_PLUGIN_ROOT}/scripts/`, each usable on its own (`--help`): `extract_task_ids.py`
(tasks, filters, one-off spreadsheet), `fetch_pr_files.py` (diffs, with a cache for closed PRs),
`score_doc_impact.py` (impact levels), `track_changes.py` (tracked list) and `run_tracking.py` (all of it).
