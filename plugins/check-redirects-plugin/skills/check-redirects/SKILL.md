---
name: check-redirects
description: Build this docs repo and produce clickable local test URLs for redirect entries (redirects/*.txt) added or changed in a commit. Use when the user wants to test/verify a redirect, check a recently pulled branch's redirect commit, or asks "give me the URLs to test" for a page rename/move.
---

# Check Redirects

Turns a commit that touches `redirects/*.txt` into a ready-to-click list of local test
URLs, after rebuilding the docs and serving them locally.

## Workflow

### 1. Identify the target commit

Default to the most recent commit on the current branch (`HEAD`). If the user names a
branch, `git checkout` it first (and `git pull` if they mention pulling). If they name a
specific commit/SHA, use that instead of HEAD.

```bash
git log -1 --oneline
```

### 2. Extract the redirect changes from that commit

Find which `redirects/*.txt` file(s) changed and what lines were added:

```bash
git show <sha> --stat -- redirects/
git show <sha> -- redirects/
```

Parse only **added** lines (`+` prefix, ignore comments/blank lines). Each line is
`<old_path>.rst <new_path>.rst` relative to `content/`. Also check the same commit for
renamed files, since redirects are usually paired with a rename:

```bash
git show <sha> --diff-filter=R --summary
```

If there are multiple redirect lines in the commit, handle all of them.

### 3. Find parent/linking pages (optional but useful)

For each new path, grep the docs for pages that link to it via `:doc:` or a `toctree`,
so the user can also verify those links weren't left dangling:

```bash
grep -rn "new_page_name" content/ --include=*.rst
```

### 4. Rebuild the docs

Run from the documentation repo root:

```bash
make clean
```

`make fast` takes a while (~1000+ source files) with no output otherwise, so run it
through `Monitor` instead of a plain background `Bash` call, to surface periodic
progress instead of going silent:

```bash
make fast 2>&1 | awk -F'[][%]' '
/^reading sources/ || /^writing output/ {
  phase = ($0 ~ /^reading/) ? "reading sources" : "writing output";
  pct = $2 + 0;
  bucket = int(pct/20);
  if (bucket != last[phase]) {
    print "Progress (" phase "): ~" (bucket*20) "%";
    last[phase] = bucket;
  }
}
/^Build finished/ { print "Build finished." }
'
```

Pass this as the `command` to `Monitor` (not `run_in_background`) with a description
like "make fast build progress" and a `timeout_ms` generous enough for a full build
(e.g. 300000). Each printed line becomes a chat notification, so the user sees ~10
progress updates (20%, 40%, ... for each phase) instead of silence, and the monitor
ends on its own once the pipe closes when `make fast` exits.

Confirm the build directory afterward — with no `VERSIONS` env var set, output lands in
`_build/html/` directly (check the `Makefile` if `VERSIONS` is ever set differently).

### 5. Serve the build locally

Start a background static server rooted at `_build/html` (so URLs don't need a
`_build/html/` prefix):

```bash
cd _build/html && python3 -m http.server 9000
```

Run this with `run_in_background: true`. If port 9000 is already bound, try 9001, 9002,
etc. Tell the user the server is running and how to stop it (kill the background shell)
when they're done testing. If the user says they'd rather use the VS Code Live Server
extension instead, skip starting a server yourself and just adjust the URLs to whatever
base URL/port Live Server is using (ask if unknown) — Live Server serves from the repo
root, so it needs the `_build/html/` prefix in the URL; a python server started inside
`_build/html` does not.

### 6. Auto-open the URLs and print them

The Claude Code terminal CLI does not render markdown links as real clickable
hyperlinks (they show up as literal text with brackets/parens), so don't rely on that
for a good UX. Instead, once the server is confirmed responding, auto-open every test
URL in the user's default browser with macOS's `open`:

```bash
open http://localhost:9000/applications/hr/recruitment/recruitment-flow.html
open http://localhost:9000/applications/hr/recruitment/recruitment_flow.html
open http://localhost:9000/applications/hr/recruitment.html
```

This pops each one into a new browser tab automatically — no clicking or copy/paste
needed. (If the user says they're on Windows/Linux, use `start` / `xdg-open` instead.)

Still also print the bare URLs as plain text (no markdown `[label](url)` wrapping — the
parentheses make them awkward to copy-paste) so the user has them for reference, e.g.
for base `http://localhost:9000/`:

```
1. Old URL (should redirect): http://localhost:9000/applications/hr/recruitment/recruitment-flow.html
2. New URL (should load directly): http://localhost:9000/applications/hr/recruitment/recruitment_flow.html
3. Parent page (check links updated): http://localhost:9000/applications/hr/recruitment.html
```

Briefly state what to expect at each: old URL auto-redirects (meta refresh) to the new
one; new URL loads the content directly; parent/linking pages contain working links to
the new path.
