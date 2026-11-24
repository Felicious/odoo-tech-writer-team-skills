# Vale results by style scope

`odoo-vale-linter` encodes the US team's rules. `run_checks.py` drops or annotates the results
that contradict the scope of the file, and lists everything it dropped under
`vale.dropped_for_scope`, so nothing disappears silently.

| Vale check | US file | Not US file | Undecided file |
|---|---|---|---|
| `Odoo.Pronouns` on *you*, *your*, *yours*, *you're* | Dropped (US Override allows *you*) | Kept | Kept, marked scope-dependent |
| `Odoo.Pronouns` on *we*, *he*, *she*, *him*, *her* | Kept | Kept | Kept |
| `Odoo.IconDescriptorFormatting` (parentheses inside `:guilabel:`) | Kept | Dropped (published format puts them outside) | Kept, marked scope-dependent |
| `Odoo.ImageAlign` | Kept (US Override: never use `:align:`) | Dropped (published guidelines allow it) | Kept, marked scope-dependent |
| `Odoo.MissingIconDescriptor` when the icon has a `:guilabel:`(name)`` descriptor | Dropped (false positive: the rule only recognizes the published format) | Kept, with a note that the descriptor exists but uses the US format | Kept |
| `Odoo.FutureTense` | Kept, with a note that US rules allow *will* when avoiding it is awkward | Kept | Kept |
| Everything else | Kept | Kept | Kept |

The `MissingIconDescriptor` false positive is a bug in the linter: its pattern accepts only
`(:guilabel:`name`)`, while `IconDescriptorFormatting` asks for `:guilabel:`(name)``. Until the
linter is fixed, the filter compensates.

When a scope changes in `agents/style_rules.md` (for example, when an Override is merged into the
published guidelines), update this table and `NOT_US_DROP` / the US rules in
`scripts/run_checks.py`.
