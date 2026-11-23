# Review report template

Fill in every section. Write "None" rather than dropping a section, so the author knows it was
checked. Number findings across the whole report (A1, A2, ... for accuracy; S1, S2, ... for
style; C1... for completeness) so the author can reply with the numbers to apply.

```markdown
# Doc quality review: <file name(s)>

**Rules applied:** `<file>`: US (published guidelines + `agents/style_rules.md`) · `<file>`: Not US
**Rule files from:** <local checkout | GitHub base branch | PR #21055 (open, not merged: rules can still change)>
**Source checked:** odoo `<branch>`, enterprise `<branch>` · docs `<branch>` (conf.py `<version>`)
**Browser check:** <off | verified on <URL>, Odoo <version>, apps: <list> | skipped: <reason>>
**Reviewed:** <changed lines only (branch vs. <base>) | whole file>

## Summary

| Quality area | Guideline | Rating (1 best – 5 worst) | Findings |
|---|---|---|---|
| Accuracy | Procedures and descriptions verified | | |
| Accuracy | Matches the current version | | |
| Accuracy | Consistent with other pages | | |
| Accuracy | References correct and relevant | | |
| Style | Scope rules (style_rules.md / published guidelines) | | |
| Style | Grammar, clarity, and tone (judgment checks) | | |
| Completeness | Possible gaps | | |

## Automated checks

| Check | Result |
|---|---|
| Build (`make fast`) | <pass | N warnings for these files | not run: reason> |
| Lint (`make test` checks) | <pass | issues> |
| Line review (line length, early breaks) | <pass | N issues> |
| Vale (scope-filtered) | <pass | N findings, M dropped for scope> |

<List line-review and Vale findings here only if they are not repeated as numbered findings below.>

## Accuracy findings

| # | Line | Problem | Suggested fix | Evidence |
|---|---|---|---|---|
| A1 | <line> | <what the page says vs. what the source shows> | <exact replacement text> | `<repo>:<path>:<line>` |

Evidence is a source `file:line`, a proof screenshot, or a docs `file:line` for consistency
issues. A finding without evidence goes under **Unverified**, not here.

## Style findings

| # | Line | Rule | Problem | Suggested rewrite |
|---|---|---|---|---|
| S1 | 35 | style_rules.md §5 *Screen location* | "top-right corner" is reversed in RTL languages | "in the top bar" |

Rule is the section of `agents/style_rules.md`, the published guideline, or "judgment" (from the
review method) for checks no rule file covers.

## Completeness: possible gaps

| # | What is not mentioned | Where it is in the source | Suggestion |
|---|---|---|---|

## Unverified: open questions

Labels, paths, and claims that neither the source nor the browser could confirm. The author lists
these in the PR description as open questions.

- Line <n>: `<label>` — <why it couldn't be confirmed>

## Existing content (not changed on this branch)

<Only when reviewing changed lines. Short list of rule breaks in unchanged lines. The author fixes
them only if the task includes it.>

## Needs your judgment

- <Decisions the rules don't settle, scope questions, conflicting sources.>

## PR checklist

Copy the checklist in `agents/pr_checklist.md` into the PR description and tick it off yourself.
What this review found for each item:
- Scope (one article, or one app): <ok | spans N apps: propose a split>
- Build, lint, line review: <status from Automated checks>
- Verified on a local instance: <yes: version, apps | no: browser check was off>
- Meta description: <unchanged | changed by hand: use the rst-meta-description skill>

---
Reply with the numbers to apply (for example "A1, S1–S4"), or "all". Nothing has been edited yet.
```
