#!/usr/bin/env python3
"""Extract the checkable claims from one .rst file.

Pulls out every UI label (`:guilabel:`), menu path (`:menuselection:`), cross-reference (`:ref:`,
`:doc:`), icon, field/option list, heading, image, and the `.. meta::` block, each with its line
number. With `--base`, it also marks which lines the current branch changed, so the review can
separate new content (must follow every rule) from existing content.

Usage:
    extract_refs.py FILE [--base REF]

`--base` accepts any git ref (for example `origin/20.0`). The script diffs against the merge base
of that ref and HEAD, plus uncommitted changes.
"""

import argparse
import re
from pathlib import Path

from dqr_common import emit, fail, find_docs_repo, git, line_of, normalize_ws, strip_trailing_ui_punct

ROLE = r':{role}:`([^`]+)`'
GUILABEL = re.compile(ROLE.format(role='guilabel'))
MENU = re.compile(ROLE.format(role='menuselection'))
REF = re.compile(ROLE.format(role='ref'))
DOC = re.compile(ROLE.format(role='doc'))
ICON = re.compile(r':icon:`([^`]+)`(\s*\(?:guilabel:`[^`]*`\)?|\s*\([^)]*\))?')
FIELD_ITEM = re.compile(r'^(\s*)[-*] :guilabel:`([^`]+)`(?:\s*:icon:`[^`]+`)*\s*:(?:\s+(.*)|$)')
# A :guilabel: used for an element the US rules put in italics (tabs, sections, windows, reports).
ITALIC_ELEMENT = re.compile(
    r':guilabel:`([^`]+)`\s+(tabs?|sections?|pages?|windows?|pop-ups?|pop-overs?|reports?|dialogs?)\b',
    re.I,
)
HEADING_CHARS = '=-~*^'
IMAGE = re.compile(r'^(\s*)\.\. (image|figure):: (\S+)')
LINK_TARGET = re.compile(r'^(?P<text>.*?)\s*<(?P<target>[^>]+)>$', re.S)


def changed_lines(docs, rel, base):
    """Lines added or modified relative to the merge base of `base`, plus uncommitted edits."""
    merge_base = git(docs, 'merge-base', base, 'HEAD')
    if not merge_base:
        return None
    diff = git(docs, 'diff', '-U0', merge_base.strip(), '--', rel) or ''
    lines = set()
    deletions = set()
    for match in re.finditer(r'^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', diff, re.M):
        old_count = int(match.group(1) or 1)
        start, count = int(match.group(2)), int(match.group(3) or 1)
        lines.update(range(start, start + count))
        if old_count and not count:
            deletions.add(start)  # text removed after this line (a move shows up as delete + add)
    return {'lines': sorted(lines), 'deletions_after': sorted(deletions)}


def split_target(body):
    match = LINK_TARGET.match(body)
    if match:
        return normalize_ws(match.group('text')), match.group('target').strip()
    return None, body.strip()


def headings(lines):
    out = []
    for i in range(1, len(lines)):
        under = lines[i].rstrip()
        title = lines[i - 1].rstrip()
        if (
            under and title.strip() and len(set(under)) == 1 and under[0] in HEADING_CHARS
            and len(under) >= 3 and not title.startswith(' ')
            and not (len(set(title.strip())) == 1 and title.strip()[0] in HEADING_CHARS)
        ):
            out.append({'line': i, 'text': title.strip(), 'char': under[0]})
    return out


def field_lists(lines):
    """Consecutive `- :guilabel:`X`: description` bullets, grouped."""
    groups = []
    open_groups = {}  # indent -> group; nested lists don't close their parent list
    current = None
    for idx, raw in enumerate(lines, start=1):
        match = FIELD_ITEM.match(raw)
        if match:
            indent = len(match.group(1))
            item = {'line': idx, 'label': match.group(2), 'description': (match.group(3) or '').strip()}
            for deeper in [i for i in open_groups if i > indent]:
                del open_groups[deeper]
            if indent in open_groups:
                open_groups[indent]['items'].append(item)
            else:
                open_groups[indent] = {'start_line': idx, 'indent': indent, 'items': [item]}
                groups.append(open_groups[indent])
            current = open_groups[indent]
            continue
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        if current and indent >= current['indent'] + 2 and not raw.lstrip().startswith(('-', '*', '#.', '..')):
            current['items'][-1]['description'] += ' ' + raw.strip()
            continue
        # Anything at or left of a list's indent closes that list (and deeper ones).
        for level in [i for i in open_groups if i >= indent]:
            del open_groups[level]
        current = open_groups[max(open_groups)] if open_groups else None
    for group in groups:
        group.pop('indent')
    return [g for g in groups if len(g['items']) >= 2]


def images(lines):
    out = []
    i = 0
    while i < len(lines):
        match = IMAGE.match(lines[i])
        if not match:
            i += 1
            continue
        indent = len(match.group(1))
        entry = {'line': i + 1, 'kind': match.group(2), 'path': match.group(3), 'alt': None, 'align': None}
        j = i + 1
        while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > indent):
            opt = re.match(r'\s*:(alt|align):\s*(.*)', lines[j])
            if opt:
                entry[opt.group(1)] = opt.group(2).strip()
            if not lines[j].strip() and j + 1 < len(lines) and not lines[j + 1].startswith(' ' * (indent + 1)):
                break
            j += 1
        out.append(entry)
        i = j
    return out


def meta_block(lines):
    for idx, raw in enumerate(lines, start=1):
        if raw.startswith('.. meta::'):
            end = idx
            while end < len(lines) and (lines[end].startswith(' ') or not lines[end].strip()):
                if not lines[end].strip() and end + 1 < len(lines) and not lines[end + 1].startswith(' '):
                    break
                end += 1
            return {'start_line': idx, 'end_line': end}
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('file')
    parser.add_argument('--base', help='Git ref to diff against (for example origin/20.0)')
    args = parser.parse_args()

    path = Path(args.file).resolve()
    if not path.is_file():
        fail(f'No such file: {args.file}')
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    docs = find_docs_repo(path)
    rel = str(path.relative_to(docs)) if docs else str(path)

    def collect(pattern, build):
        return [build(m) for m in pattern.finditer(text)]

    guilabels = collect(GUILABEL, lambda m: {
        'line': line_of(text, m.start()),
        'text': normalize_ws(m.group(1)),
        # Icon descriptors are written `(clock)`; the parentheses are formatting, not UI text.
        'compare_as': strip_trailing_ui_punct(re.sub(r'^\((.*)\)$', r'\1', normalize_ws(m.group(1)))),
    })

    def build_menu(m):
        raw = normalize_ws(m.group(1))
        segments = [s.strip() for s in raw.split('-->')]
        first = segments[0]
        app_suffix = bool(re.search(r'\s+app$', first, re.I))
        return {
            'line': line_of(text, m.start()),
            'text': raw,
            'segments': segments,
            'menu_segments': [re.sub(r'\s+app$', '', first, flags=re.I), *segments[1:]],
            'starts_with_app_suffix': app_suffix,
        }

    menus = collect(MENU, build_menu)

    def build_link(m):
        label, target = split_target(m.group(1))
        return {'line': line_of(text, m.start()), 'text': label, 'target': target}

    changes = changed_lines(docs, rel, args.base) if (args.base and docs) else None
    data = {
        'file': rel,
        'line_count': len(lines),
        'changed_lines': changes['lines'] if changes else None,
        'deletions_after': changes['deletions_after'] if changes else None,
        'meta': meta_block(lines),
        'headings': headings(lines),
        'guilabels': guilabels,
        'menuselections': menus,
        'refs': collect(REF, build_link),
        'docs': collect(DOC, build_link),
        'icons': collect(ICON, lambda m: {
            'line': line_of(text, m.start()),
            'icon': m.group(1),
            'descriptor': normalize_ws(m.group(2) or '') or None,
        }),
        'field_lists': field_lists(lines),
        'guilabel_for_italic_element': collect(ITALIC_ELEMENT, lambda m: {
            'line': line_of(text, m.start()), 'label': normalize_ws(m.group(1)), 'element': m.group(2).lower(),
        }),
        'images': images(lines),
    }
    if args.base and changes is None:
        data['warning'] = f'Could not compute a merge base with {args.base}; changed_lines is unknown.'
    emit(data)


if __name__ == '__main__':
    main()
