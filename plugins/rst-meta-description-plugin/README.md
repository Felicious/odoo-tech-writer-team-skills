# rst-meta-description-plugin

Generates or fixes the `.. meta::` description field for a single Odoo
documentation `.rst` file, to improve the page's readability for LLM-based
agents and answer engines.

## Usage

```
/rst-meta-description-plugin:rst-meta-description
```

Point Claude at the `.rst` file you're working on. Natural language prompts
such as, "make a description for <filename>.rst" should suffice. If it's
ambiguous which file that is, Claude will ask before doing anything else.

Claude will read the file, flag whether it's missing a description, using
the wrong (bare `:description:`) syntax, or already has a proper one, then
ask which points from the page you'd like to highlight before drafting
anything. You can pick from what it found, suggest your own emphasis, or
let it decide unprompted.

The description is written directly to the file. Review the change with
`git diff` before committing — Claude does not ask for in-chat approval of
the wording first.

## Requirements

- Python 3 (standard library only — no `pip install` needed; the bundled
  `scripts/rst_meta.py` uses only `argparse`, `re`, and `json`)

## Notes

- The description is generated only from the target file's own content —
  it does not consult other pages, a separate style guide, or outside
  knowledge about the feature being documented.
- Content rules are enforced regardless of file: no future tense, no
  second person, max 100 characters per line (RST multi-line field-body
  wrapping), and length aimed at LLM comprehension rather than
  search-engine snippet cutoffs.
- Claude flags low confidence when a page has too little prose, is very
  short, or has ambiguous headings — it still drafts a description in
  these cases, just calls out that it should get extra scrutiny.
