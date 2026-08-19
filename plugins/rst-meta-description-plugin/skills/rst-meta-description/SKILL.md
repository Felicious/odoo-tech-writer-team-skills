---
name: rst-meta-description
description: Generate or fix the LLM-readability meta description for a single Odoo documentation .rst file — the one currently open/being worked on in the editor. Use this whenever the user asks to add, fix, generate, or check a meta description for an RST doc page, mentions ".. meta::", asks about a page missing a description, or references the bare ":description:" field bug in an RST file. Always confirm which file is the target if multiple are open before running.
---

# RST Meta Description Generator

Generates a `.. meta::` description block for a single Odoo `.rst` documentation
file, sourced only from that file's own content, following Odoo's content
style rules. Writes the change directly to the file — the user reviews it via
`git diff` before committing, not via an in-chat approval step.

Detection, key-point extraction, line-wrapping, and file writing are all
handled by the bundled script (`${CLAUDE_PLUGIN_ROOT}/scripts/rst_meta.py`) —
these are mechanical,
deterministic steps with no judgment involved, so they never need to pass
through the model. The model's only job is composing the description text
itself, and running a quick style/rule check on it before handing it to the
script to format and write.

## Scope

This skill operates on **exactly one file**: whichever `.rst` file the user is
currently working on. If it's unclear which file that is (e.g. multiple files
open in different tabs, or the user hasn't named one), ask which file before
doing anything else. Do not scan folders or process multiple files — that is
explicitly out of scope for this skill.

## Workflow

1. **Identify the target file.** Confirm with the user if ambiguous.

2. **Run the analyzer** to detect state and extract candidate material:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rst_meta.py analyze <file>
   ```

   This returns JSON with:
   - `state`: `"missing"`, `"bare_field"`, or `"proper_meta"`
   - `existing_description`: current description text, if any
   - `headings`: the file's section headings, in order
   - `candidate_points`: a list of `{label, text}` pairs — one per heading,
     each paired with the first sentence of the paragraph that follows it,
     plus one for the page's intro paragraph. This is pure pattern
     extraction, not summarization — the script doesn't decide what's
     important, it just surfaces raw material for the user to react to.

   If `state` is `"proper_meta"`, tell the user a description already
   exists (show `existing_description`) and ask whether they want it
   regenerated anyway before continuing.

3. **Ask the user what to highlight, before drafting anything.** Present
   the `candidate_points` from step 2 as options, and give the user a way
   to write in something else instead. For example, offer the headings/
   candidate sentences as selectable options alongside a free-text
   "something else" option. The user may pick one or more candidates,
   supply their own emphasis, or decline and let the model decide
   unprompted — all are valid. Don't skip this step even if the file seems
   short or the intent seems obvious; it's cheap to ask and the user may
   want emphasis on something the extraction missed (extraction is
   headings + first sentences only, so it can miss the actual point of a
   section).

4. **Compose the description**, incorporating whatever the user chose to
   highlight, and following the content rules below. This is the one part
   of the workflow that requires judgment and stays with the model.

5. **Write the change** by handing the finished text to the script:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rst_meta.py write <file> --description "TEXT"
   ```

   This single call handles everything mechanical: removing a bare
   `:description:` field if present, removing/replacing an existing
   `.. meta::` block if regenerating, wrapping the text to 100 chars/line
   using RST multi-line field-body syntax, and inserting the block at the
   very top of the file. Do not hand-format or hand-edit the RST yourself —
   that's what the script is for.

6. **Report back** with a single confirmation that the block was written,
   plus any flags from the section below.

## Content rules (hard constraints)

These are non-negotiable Odoo content rules. Apply all of them:

- **Source material**: draw only from the file's own text (title, headings,
  body prose). Do not infer, assume, or supplement with outside knowledge
  about the feature being documented.
- **Length**: sized for LLM comprehension, not search-engine display —
  don't optimize for a ~155-character search-snippet cutoff. A solid target
  is roughly 1–2 sentences that summarize what the page covers and what a
  reader accomplishes by following it. If in doubt, shorter and precise
  beats long and padded.
- **Line wrapping**: handled automatically by `${CLAUDE_PLUGIN_ROOT}/scripts/rst_meta.py write` —
  compose the description as a normal single string; the script wraps it
  to a max of 100 characters per line using correct RST multi-line
  field-body indentation. No need to insert line breaks manually.

- **No future tense**: not just avoiding the word "will" — avoid future
  tense generally. Prefer present tense ("this page explains," "renewal
  creates a new quotation") over future framing ("this page will explain,"
  "a new quotation will be created").
- **No second person**: never use "you." Resolve this however reads most
  natural for the specific sentence — passive voice, third person, or an
  imperative/infinitive framing are all acceptable; there's no single
  required substitution. Pick per-sentence, not a fixed template.
- **Style pattern-matching**: mirror the terminology and phrasing
  conventions already present in the file itself (e.g. if the file uses
  "guilabel"-style UI references, or a particular verb pattern like
  "navigate to X app," echo that same register in the description). Do not
  pull conventions from any file or reference other than the one being
  edited.

## Confidence flagging

Always generate a description — never skip generation entirely — but flag
low confidence to the user when:

- The file has too little prose to summarize (mostly tables, images, or
  reference material with little running text).
- The file is very short (a stub page).
- The headings are ambiguous or don't clearly indicate what the page
  actually covers, making it hard to be sure the summary is accurate.

Separately, flag it if applying the hard content rules (length, no future
tense, no second person, line wrap) forces an awkward or unsatisfactory
result — for example if avoiding "you" makes a sentence stilted, or if the
page's subject matter doesn't compress well into a short description without
losing clarity. Don't silently produce a bad description to satisfy the
rules; say so.

## Messaging

Regardless of which of the three detection states triggered the write (no
description found, bare field replaced, or regeneration requested), use one
generic confirmation once the file is written — don't produce different
templated messages per case. Something like: "Added a meta description to
`<file>`. Review the diff before committing." Append any confidence/quality
flags from the section above to that same message.

## What this skill does not do

- Does not scan directories or batch-process multiple files.
- Does not consult any external style guide, prior Odoo docs, or the
  broader repo for conventions — only the target file's own content.
- Does not ask for in-chat approval of the generated *text* before
  writing — the user's review step is `git diff`, after the fact. (The
  highlight-selection step in the workflow above is about what to
  emphasize, not a preview/approval of the final wording.)
- Does not optimize the description for search-engine snippet length.
- Does not hand-format the RST output — `${CLAUDE_PLUGIN_ROOT}/scripts/rst_meta.py` owns all
  detection, extraction, wrapping, and file writing; the model only
  composes the description string.

## Script reference

`${CLAUDE_PLUGIN_ROOT}/scripts/rst_meta.py` has two subcommands:

- `analyze <file>` — read-only. Reports detection state, any existing
  description text, the file's headings, and pattern-extracted candidate
  highlight points. Safe to run freely.
- `write <file> --description "TEXT"` — mutates the file. Removes any
  existing bare field or `.. meta::` block, wraps TEXT to 100 chars/line
  with correct RST indentation, and inserts the new block at the top of
  the file.

Nothing in the script makes judgment calls about content, tone, or
accuracy — it only detects existing markup, extracts headings/first
sentences verbatim, formats line-wrapping, and performs file I/O.
