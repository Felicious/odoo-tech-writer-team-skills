# Review method and judgment checks

Source: Hargis et al., *Developing Quality Technical Information: A Handbook for Writers and
Editors*, 2nd ed. (IBM Press, 2004). Chapter 3 (Accuracy), Chapter 7 (Style), and Chapter 12
(Reviewing, testing, and evaluating). The checklists below are paraphrased and adapted to Odoo.
The odoo/documentation rule files take precedence over anything here.

## How to review (Chapter 12)

- **Read as the user.** For every passage, ask: if I were the reader, could I find this,
  understand it, and do the task with it? A reviewer who already knows the feature tends to fill
  gaps that a reader cannot.
- **Use the product.** Check the text against the product (here, the source code, and the running
  instance when the browser check is on). Don't review the words in isolation.
- **Be specific and give the fix.** "This is wrong" is not a finding. Say what is wrong, where,
  why, and what to write instead. When there is more than one valid fix, give the reasoning so the
  writer can choose.
- **Split the roles.** A technical reviewer judges accuracy and completeness. An editor judges
  style and clarity. Keep the passes separate so one doesn't color the other.
- **Rate, then summarize.** After listing findings, rate each guideline from 1 to 5 based on the
  number and severity of the findings, and collect the ratings in one summary.

Rating scale (the book's): **1** very satisfied, **2** satisfied, **3** neutral, **4**
dissatisfied, **5** very dissatisfied. Lower is better.

## Accuracy (Chapter 3)

Inaccurate docs destroy trust: after finding one error, readers stop relying on the docs and call
support. Errors that look plausible do the most damage, because readers act on them.

| Guideline | What to check in an Odoo page | How |
|---|---|---|
| Verify what you write | Each procedure works when followed: every menu path, button, and field exists, in that order, and the steps lead to the result described. Descriptions of behavior are true. | `verify_ui_refs.py`, then read the source for behavior claims (defaults, automation, access, module installs). Browser check when enabled. |
| Keep up with changes | The page matches the current version: no removed or renamed fields, settings, menus, or options. Screenshots and examples match the current UI. References to other products and apps are current. | `case_mismatch`, `not_found`, and `partial` results. Compare screenshot content with the labels in the source. |
| Keep information consistent | The same feature is described the same way on every page. Examples match the text and the real output. | `git grep` the docs for the same labels and feature names, and compare what other pages say. |
| Automate what you can | Spelling and grammar errors are gone from text, examples, and code samples. | `run_checks.py` (lint, line review, Vale). |
| Check references | Every `:ref:` and `:doc:` target exists **and** covers what the link text promises. | `verify_ui_refs.py` links output, then open each target and read the section. |

## Completeness (Chapter 4, applied lightly)

Use `view_checks.py settings` to list settings and sections the page never mentions. These are
*possible* gaps. Report them only when the page claims to cover that screen (for example, a
Configuration section that walks through the settings page), and say which other page might
cover them instead.

## Style: judgment checks the rule files don't cover (Chapter 7)

The odoo/documentation rule files cover tone, tense, mood, word choice, formatting, lists, and
highlighting in detail, so apply those first. These checks are left for human-style judgment:

- **Sentence fragments** in paragraphs (outside list items and labels).
- **Dangling or misplaced modifiers:** "After enabling the setting, the kiosk shows..." (the kiosk
  didn't enable anything).
- **Vague pronouns:** *it*, *this*, *that* with no clear noun. Common after a long sentence or at
  the start of a paragraph.
- **That vs. which:** *that* for restrictive clauses (no comma), *which* after a comma for
  nonrestrictive ones.
- **Passive voice that hides who acts:** "The attendance is validated" — by the manager, or by
  Odoo automatically? Passive voice is fine when the actor is obvious or unimportant.
- **Commonly confused words:** *ensure/insure*, *affect/effect*, *setup/set up*, *login/log in*,
  *checkout/check out* (noun vs. verb).
- **Consistent terms:** one name per concept within a page and across related pages.
- **Parallel lists:** every item in a list has the same grammatical form (US rules require this
  for field lists; apply it to all lists).
- **Consistent tone** across the page.

Do **not** flag singular *they*. The book (2004) calls it incorrect; current Odoo usage and modern
style guides accept it.
