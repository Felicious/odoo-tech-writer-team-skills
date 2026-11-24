#!/usr/bin/env python3
"""Decide which style rules apply to each .rst file, from `agents/docs_ownership.md`.

Scopes:
- US: published guidelines + `agents/style_rules.md` (its Override rules win).
- NOT_US: published guidelines only.
- UNDECIDED: listed as undecided, or an index page whose folder spans both scopes. Ask the user.
- UNLISTED: no rule matches. Treat like UNDECIDED and ask the user.

The ownership file is prose, so the parser is a heuristic. Every result includes the rule line it
matched, so the reviewer can sanity-check it.

Usage:
    scope_for_path.py --ownership agents/docs_ownership.md FILE [FILE ...]
    scope_for_path.py --ownership agents/docs_ownership.md --dump-rules
"""

import argparse
import re
from pathlib import Path

from dqr_common import emit, fail, find_docs_repo

APPS = 'content/applications/'
SECTION_SCOPES = [('not us', 'NOT_US'), ('us scope', 'US'), ('undecided', 'UNDECIDED')]
BACKTICK = re.compile(r'`([^`]+)`')


def resolve(token):
    token = token.strip()
    return token if token.startswith('content/') else APPS + token


def parse_bullets(text):
    """Yield (scope, bullet_text) for each top-level bullet under a scope heading."""
    scope = None
    current = None
    for raw in text.splitlines():
        if raw.startswith('## '):
            if current:
                yield scope, current
                current = None
            heading = raw[3:].strip().lower()
            scope = next((s for key, s in SECTION_SCOPES if heading.startswith(key)), None)
            continue
        if scope is None:
            continue
        if raw.startswith('- '):
            if current:
                yield scope, current
            current = raw[2:].strip()
        elif current and raw.startswith('  ') and raw.strip():
            current += ' ' + raw.strip()
        elif not raw.strip() and current:
            yield scope, current
            current = None
    if current:
        yield scope, current


def rules_from_bullet(scope, bullet):
    """Turn one bullet into a list of (path, scope, bullet) rules. Folder paths end with `/`."""
    rules = []
    tokens = BACKTICK.findall(bullet)
    if not tokens:
        return rules

    if bullet.lower().startswith('outside'):
        # "Outside `content/applications/`: `content/administration/`, ..."
        for token in tokens[1:]:
            rules.append((resolve(token), scope, bullet))
        return rules

    if not bullet.startswith('`'):
        # Prose bullet with examples, e.g. "Category index pages ..., such as `finance.rst`".
        for token in tokens:
            rules.append((resolve(token), scope, bullet))
        return rules

    first = tokens[0]
    base = resolve(first)
    rest = bullet[bullet.index('`', 1) + 1:]

    if rest.lstrip().startswith('(all)') or not rest.strip():
        rules.append((base, scope, bullet))
    elif rest.lstrip().startswith(':'):
        items = rest.split(':', 1)[1]
        items = re.sub(r'\([^)]*\)', '', items)  # drop "(including payroll localizations)"
        for item in items.split(','):
            item = item.strip().strip('.')
            if not item:
                continue
            name = item.strip('`')
            if name.endswith('.rst') or '/' in name:
                rules.append((base + name, scope, bullet))
            else:
                rules.append((base + name + '/', scope, bullet))
    else:
        rules.append((base, scope, bullet))

    # "`essentials/`, including `essentials/property_fields.rst`"
    if re.search(r'\b(including|such as)\b', rest):
        for token in tokens[1:]:
            rules.append((resolve(token), scope, bullet))
    return rules


def load_rules(ownership_path):
    text = Path(ownership_path).read_text(encoding='utf-8')
    rules = []
    for scope, bullet in parse_bullets(text):
        rules.extend(rules_from_bullet(scope, bullet))
    return rules


def rule_matches(rule_path, file_path):
    if rule_path.endswith('/'):
        return file_path.startswith(rule_path) or file_path == rule_path[:-1] + '.rst'
    return file_path == rule_path


def scope_for(file_path, rules):
    matches = [r for r in rules if rule_matches(r[0], file_path)]
    if matches:
        path, scope, bullet = max(matches, key=lambda r: len(r[0]))
        return {'scope': scope, 'matched_rule': path, 'rule_text': bullet}

    # An index page (`x.rst` next to folder `x/`) whose folder spans several scopes.
    if file_path.endswith('.rst'):
        folder = file_path[:-4] + '/'
        inner = {r[1] for r in rules if r[0].startswith(folder)}
        if len(inner) > 1:
            return {
                'scope': 'UNDECIDED',
                'matched_rule': folder,
                'rule_text': f'Index page whose folder spans several scopes: {sorted(inner)}',
            }
        if len(inner) == 1:
            return {
                'scope': inner.pop(),
                'matched_rule': folder,
                'rule_text': 'Index page whose folder contents all share one scope',
            }

    return {'scope': 'UNLISTED', 'matched_rule': None, 'rule_text': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ownership', required=True, help='Path to agents/docs_ownership.md')
    parser.add_argument('--docs-repo')
    parser.add_argument('--dump-rules', action='store_true')
    parser.add_argument('files', nargs='*')
    args = parser.parse_args()

    rules = load_rules(args.ownership)
    if not rules:
        fail(f'No rules parsed from {args.ownership}. Has its format changed?')
    if args.dump_rules:
        emit([{'path': p, 'scope': s} for p, s, _ in rules])
        return

    docs = find_docs_repo(args.docs_repo or (args.files[0] if args.files else None))
    results = []
    for f in args.files:
        path = Path(f).resolve()
        rel = str(path.relative_to(docs)) if docs and path.is_relative_to(docs) else f
        results.append({'file': rel, **scope_for(rel, rules)})
    emit(results)


if __name__ == '__main__':
    main()
