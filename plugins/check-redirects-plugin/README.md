# check-redirects-plugin

Turns a commit that touches `redirects/*.txt` in the `odoo/documentation`
repo into a ready-to-click list of local test URLs, after rebuilding the
docs and serving them locally.

## Usage

```
/check-redirects
```

If another skill or command named `check-redirects` is also installed (for
example, a copy in the docs repo's `.claude/skills/`), the short name is
ambiguous. Remove the duplicate, or use the full name
`/check-redirects-plugin:check-redirects`.

Run it from the root of your `odoo/documentation` clone. By default it checks
the most recent commit on the current branch (`HEAD`). You can also name a
branch (Claude checks it out, and pulls if you ask) or a specific commit SHA.

Claude will:

1. Read the added redirect rules (and any paired file renames) from the commit.
2. Find pages that link to the new paths via `:doc:` or `toctree`.
3. Run `make clean` and `make fast`, reporting build progress as it goes.
4. Serve `_build/html` on `http://localhost:9000` (or the next free port).
5. Open each test URL in your default browser and print them as plain text:
   the old URL (should redirect), the new URL (should load directly), and any
   linking pages (should have working links to the new path).

## Requirements

- A local clone of `odoo/documentation` with its Python environment set up
  (`pip install -r requirements.txt`), so `make fast` works
- Python 3 (for the local `http.server`)
- macOS `open` to launch URLs (on Windows/Linux, tell Claude so it uses
  `start` / `xdg-open` instead)

## Notes

- A full build takes several minutes. The local server keeps running in the
  background until you stop it; Claude tells you how.
- Prefer the VS Code Live Server extension? Say so, and Claude skips starting
  a server and adjusts the URLs (Live Server serves from the repo root, so the
  URLs need a `_build/html/` prefix).
