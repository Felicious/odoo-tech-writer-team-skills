---
name: doc-quality-review
description: Reviews Odoo documentation .rst files for accuracy and style. Checks every UI label, menu path, setting, option list, and cross-reference against the odoo/odoo and odoo/enterprise source code, applies the US or Not US style rules from odoo/documentation (AGENTS.md, agents/style_rules.md, agents/docs_ownership.md) per file, runs the lint, line review, and Vale checks, and returns numbered findings with evidence and proposed fixes, without editing anything until the author approves. Optionally verifies the page in a running Odoo instance (--browser). Use when the user asks to review, QA, proofread, fact-check, or check the accuracy or style of a docs page, a docs folder, or the docs changed on their branch, or asks whether a page matches the code or the UI. Not for writing PR descriptions (use pr-summarizer) or meta descriptions (use rst-meta-description).
---

# Doc quality review

Reviews Odoo documentation pages like a technical reviewer (accuracy against the source) and an
editor (style against the team's rules), then hands the author a report with numbered findings.
The method comes from *Developing Quality Technical Information* (Hargis et al.); the rules come
from the odoo/documentation repository.

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/` (Python 3, standard library only). Below, `$S` means
that folder. References: `${CLAUDE_PLUGIN_ROOT}/skills/doc-quality-review/references/`, `$R`
below. Write all intermediate JSON to the scratchpad directory (or a temp directory), never into
the docs repository.

## Arguments

`$ARGUMENTS` can contain:

- `.rst` files or folders to review. Review **only** these (AGENTS.md: stay scoped).
- `--branch`: review the `.rst` files changed on the current branch instead. Use only when asked.
- `--browser [URL]`: turn on the browser check. **Off by default.** Also on if the user asks in
  their own words to check the page in Odoo or in the UI.
- `--build`: also run the full docs build (`make fast`). On by default with `--branch`.

No files and no `--branch`: if the user's message names files, use those; otherwise ask which
files to review. Never expand to the whole branch on your own.

## Ground rules

- **No edits before approval.** Propose every change with its line number and exact rewrite, and
  wait. Never push, commit, or open a PR.
- **Evidence or it's unverified.** An accuracy finding needs a source `file:line`, a proof
  screenshot, or a docs `file:line`. Anything else goes under *Unverified*.
- **New content follows every rule.** On a branch with changes, focus on changed lines. List rule
  breaks in unchanged lines separately and briefly. When the file has no changes, review the whole
  file, because the user asked for it.
- **Say when a tool is missing.** Never skip a check silently.

## Workflow

### 1. Load the rules

```bash
python3 $S/get_rules.py --docs-repo <docs repo> --cache-dir <scratchpad>/rules
```

It returns the paths of `AGENTS.md`, `agents/style_rules.md`, `agents/docs_ownership.md`,
`agents/pr_checklist.md`, and the published guidelines. If `warning` is set, the rules came from
GitHub (PR #21055 is not merged yet, or the checkout is behind): include the warning in the
report. If it fails, stop and show the error.

Read `AGENTS.md` now. Read the other files when a step below needs them.

### 2. Resolve files and scopes

1. List the files. With `--branch`: `git diff --name-only --diff-filter=AMR origin/<version>...HEAD -- '*.rst'`
   plus uncommitted `.rst` changes, where `<version>` is `version` from `conf.py`.
2. Get the style scope of each file:

   ```bash
   python3 $S/scope_for_path.py --ownership <docs_ownership.md> <files...> > scopes.json
   ```

3. For `UNDECIDED` or `UNLISTED` files, ask the user which rules apply (US or Not US) before
   reviewing them. Show the `rule_text` that matched. Update `scopes.json` with the answer.
4. With `--branch`, check the PR scope from `AGENTS.md`: one article, or one app if necessary,
   never more than one app. If the files span several apps, say so and propose a split, then
   continue the review.

### 3. Start the automated checks (in the background)

```bash
python3 $S/run_checks.py --scope-json scopes.json <files...> [--build] [--vale-config <path>]
```

Vale's config is found in this order: `--vale-config`, `$VALE_CONFIG`, `odoo-vale-linter/.vale.ini`
next to the docs repo, then `~/Documents/odoo/odoo-vale-linter/.vale.ini`.

Run it with `run_in_background` when `--build` is on (the build takes minutes), and continue.
It runs the CI lint, the line review, and Vale filtered by scope
(`$R/vale-scope-filter.md`), and reports `missing` for any tool that isn't installed.

### 4. Read the context

For each file, read the file **and its parent index page** (for example `attendances.rst` for
`attendances/overtime.rst`). If the file is itself an index page (it has a `toctree`), skim the
child pages it lists instead: they are where its claims are expanded or handed off. Then read the
rules for its scope:

- US: `agents/style_rules.md` (and the published guidelines it builds on).
- Not US: `content_guidelines.rst` and `rst_guidelines.rst` only. Don't apply US Overrides.

### 5. Collect the source evidence

For each file:

1. Extract the checkable claims. `<version>` is the docs version from `conf.py`:

   ```bash
   python3 $S/extract_refs.py <file> --base origin/<version> > <name>.extract.json
   ```

   `changed_lines` lists the lines changed since the merge base with `<version>`, committed or
   not. `deletions_after` marks where text was removed; a moved block shows up as a deletion
   plus an addition, so read `git diff origin/<version> -- <file>` when either list is
   surprising. If both are empty, the file has no changes: review the whole file.
2. Pick the modules for the page (see *Find the modules* in `$R/source-lookup.md`), for example
   `'hr_attendance*'`. The scripts always search both repositories in full; `--modules` only
   ranks the evidence and limits `view_checks.py`. Don't add `base`, `web`, or `hr` just for
   generic labels (Save, Settings, Access Rights).
3. Check labels, menu paths, and links:

   ```bash
   python3 $S/verify_ui_refs.py <name>.extract.json --modules '<pattern>' ... > <name>.verify.json
   ```

   If `repos.version_mismatch` is not empty, stop and tell the user which repository is on which
   branch. Don't switch branches yourself. Offer to continue anyway only with a warning on every
   accuracy finding.
4. Check settings coverage and list order:

   ```bash
   python3 $S/view_checks.py settings --modules '<pattern>' --docs <file> <file's folder, if any>
   python3 $S/view_checks.py order <name>.extract.json --list <i> --modules '<pattern>'   # for each field list
   ```

### 6. Review: two passes in parallel

Launch two subagents in one message, so the style pass isn't anchored by the accuracy pass. For
more than three files, give each pair a batch of files. Give each one the absolute paths it needs
(the files, the JSON outputs, the rule files, the references), and ask it to return findings as a
list of `{line, problem, fix, evidence_or_rule, changed_line: bool}`.

**Accuracy reviewer** (technical reviewer). Brief it with:
- The file, its parent page, and the extract, verify, and view-check JSON.
- `$R/source-lookup.md` and the *Accuracy* and *Completeness* sections of `$R/book-checks.md`.
- Tasks:
  - For every label that is `not_found`, `weak`, or `case_mismatch`, every menu that is `partial`
    or `app_not_found`, and every list with a different order: read the source and decide.
    Labels with `generic: true` prove little; check them in context.
  - Check the claims in the prose that the scripts can't: defaults, what a setting does, which
    module a setting installs, which access group is needed, and what Odoo does automatically.
  - Check every stated condition against the view: each "when X is selected / enabled, Y
    appears" sentence must match the `invisible=` (or `groups=`) expression on Y. The scripts
    confirm that X and Y exist, not how they relate.
  - For a list where `view_checks.py order` returns a `note` (no source match), find where the
    options come from by hand (for example `res.groups` names for access rights).
  - Search the docs for other pages that describe the same features (`git grep` the labels),
    and report contradictions.
  - Open each `:ref:` and `:doc:` target and confirm it covers what the link text promises.
  - From the settings output, report possible gaps only where the page claims to cover that
    screen.
  - Every finding cites `repo:path:line`. If it can't be confirmed in the source, it's
    unverified, with a note on what the browser check should look at.

**Editor** (style). Brief it with:
- The file, its scope, and the rule files for that scope.
- The Vale and line-review results for the file from step 3, if ready (if not, it reviews
  without them and you merge them later).
- The *Style* section and *How to review* section of `$R/book-checks.md`.
- Tasks:
  - US files: go through `agents/style_rules.md` §15 *Review checklist* item by item, then the
    rest of the file. Override rules win over the published guidelines.
  - Not US files: the published guidelines only. Don't apply US-only rules (numbered
    `(optional)` steps, *you*, `Sales app -->` menu paths, italic section titles, and the other
    Overrides).
  - Then the judgment checks from `$R/book-checks.md`.
  - Use the extract JSON for the mechanical US checks: `guilabel_for_italic_element` (tabs,
    sections, windows, and reports in `:guilabel:` instead of italics) and
    `menuselections[].starts_with_app_suffix` (US paths need `<App> app -->`; Not US paths must
    not have it).
  - Flag a changed `.. meta::` description (it must come from the rst-meta-description skill).
  - Every finding names its rule (`style_rules.md §5`, `content_guidelines.rst`, or "judgment")
    and gives the exact rewrite. Separate changed lines from unchanged ones.

### 7. Browser check (opt-in)

Only if turned on (see *Arguments*). Follow `$R/browser-check.md`: get the URL from the author,
check the version with `instance_info.py`, use a test database, and check only what the source
couldn't settle. When it's off, leave the items that need the UI on the *Unverified* list and
mention `--browser` once at the end of the report.

### 8. Report

1. Collect the background checks from step 3. If the build hasn't finished, report it as still
   running and update the report when it does.
2. Merge the findings and remove duplicates (Vale and the editor often agree). When one passage
   has both an accuracy problem and style problems, keep one finding in *Accuracy* and name the
   style rules in it, because the accuracy fix usually rewrites the passage. Drop any accuracy
   finding that has no evidence; move it to *Unverified*.
3. Check a sample of the findings yourself before reporting, especially `not_found` labels and
   anything surprising. A wrong finding costs the author more than a missed one.
4. Rate each guideline 1–5 (1 best):
   - **1:** no findings.
   - **2:** minor findings only (wording, formatting).
   - **3:** several minor findings, or one that could mislead.
   - **4:** more than one finding that misleads or breaks a step.
   - **5:** the page can't be followed or trusted as written.
5. Write the report with `$R/handoff-template.md`. Number the findings.
6. Wait. When the author picks findings to apply, edit only those, then rerun
   `run_checks.py` on the changed files and report the result. Remind the author to copy
   `agents/pr_checklist.md` into the PR description.
