---
name: pr-summarizer
description: >
  Draft a pull request description from local branch changes in a documentation
  repository. Use this skill whenever the user wants to create a PR description,
  summarize what changed on a branch, or prepare a write-up before opening a PR.
  Trigger for phrases like "write a PR description", "summarize my branch changes",
  "help me write a PR", "what changed on my branch", "draft a PR", or any request
  to document or describe local branch changes for a pull request. The PR does not
  need to exist yet. Assumes the user is running from within their local repository.
---

# PR Summarizer Skill

Reads changes on a local Git branch and produces a GitHub-ready PR description
in markdown — covering what changed, why, and a grouped list of specific changes
(including deleted and renamed files).

---

## Step 1 — Gather Inputs

You need four things:

| Input | How to get it |
|-------|--------------|
| **Repo path** | Run `git rev-parse --show-toplevel` to find the repo root from CWD. Use that unless the user specifies a different path. |
| **Feature branch** | The branch with the new changes. If not provided, run `git branch` and ask. |
| **Base branch** | Always ask the user — do not assume or auto-detect. |
| **FWP branch** | The furthest branch this PR can be forward-ported to. Always ask — do not skip or assume. |

---

## Step 2 — Collect the Diff

```bash
bash <skill_dir>/scripts/collect_diff.sh <repo_path> <feature_branch> <base_branch>
```

The script outputs:
- File change stats + name-status (catches renames and deletes)
- Commit messages on the branch
- Full diff (lock files and build artifacts excluded; truncated per-file if >150 KB)

---

## Step 3 — Generate the PR Description

Produce a single GitHub-formatted PR description using this template:

```markdown
## What this PR does and why it's needed
<1-3 sentences describing the purpose, outcome, and motivation. What documentation is being added, updated, or restructured? Be specific. Are they new feature docs, outdated content, reorganization, fixing errors, etc.? Infer from the diff and commit messages.>

## Changes

**<Functional group — e.g. "Getting Started", "API Reference", "Tutorials", "Navigation", "Configuration">**
- <Specific change — what was added, updated, or removed and why>
- <Another change>

**<Another group>**
- ...

### Deleted files
- `path/to/file.md` — <reason if inferrable from context>

### Renamed / moved files
- `old/path.md` → `new/path.md`

---
This `<base_branch>` PR can be FWP up to `<fwp_branch>`.
```

**Rules:**
- Ask user if this is based on feedback; if so, add to "What this PR does" section
- Group by documentation area or topic (not file type)
- Each bullet: specific and concrete — "Added installation steps for Windows" not "updated install.md"
- Merge any group with only one bullet into the nearest related group
- Only include Deleted / Renamed sections if those changes actually exist
- Mirror terminology from the commit messages and file names
- Only document changes if they are UI-related
- Ignore small language changes like changing "since" to "before" and minor grammar changes
- Leave out figure to image replacements and icon updates
- If the user says not to FWP the branch, use `This <base_branch> PR **should not be FWP**` in place of the existing FWP statement
- If the diff was truncated, add: `> ⚠️ Diff was truncated — some changes may not be reflected above`

---

## Step 4 — Present the Output

Output the PR description as a single fenced markdown code block the user can copy directly into GitHub. Add a one-line note before it:

> Here's your PR description — ready to paste into GitHub:

## Step 5 — Copy the Output to Clipboard

Copy everything below (and including) the `DESCRIPTION` line to the clipboard:

```bash
xclip -selection clipboard << 'CLIP'
<description content>
CLIP
```

Then print to screen: `Copied to clipboard.`

## Step 6 — Open the PR Creation Page

Automatically open the GitHub compare/PR-creation page for this branch — do not just open the repo homepage, and do not ask the user first.

Derive the `owner/repo` from the origin remote, then open the compare URL for `<base_branch>...<feature_branch>`:

```bash
repo_slug=$(git -C <repo_path> remote get-url origin | sed -E 's#(git@github\.com:|https://github\.com/)##; s#\.git$##')
xdg-open "https://github.com/${repo_slug}/compare/<base_branch>...<feature_branch>?expand=1"
```

This lands the user directly on the pre-filled "Open a pull request" page with the base and feature branches already selected.

---

## Error Handling

| Problem | Resolution |
|---------|-----------|
| Not a git repo | Show git's error, ask for correct path |
| Branch not found | Run `git branch -a` and show the list |
| Diff is empty | Check divergence: `git log base..feature --oneline` |
| No commits ahead of base | Warn: branch may be up to date or already merged |
| Binary/image files in diff | Do not list individual image updates; just state that screenshots were updated |
