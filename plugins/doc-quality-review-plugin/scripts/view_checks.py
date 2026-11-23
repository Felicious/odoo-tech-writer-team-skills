#!/usr/bin/env python3
"""Checks that read Odoo view XML: settings coverage and field-list order.

Subcommands:

  settings  List every setting and settings section (`<setting>`, `<block>`) in the given
            modules' views, and report which ones the given docs never mention. Use it to find
            what a page leaves out (completeness), not as a list of errors: some settings belong
            on other pages.

      view_checks.py settings --modules 'hr_attendance*' --docs content/applications/hr/attendances.rst content/applications/hr/attendances/

  order     For one field/option list from extract_refs.py, find the views that contain those
            labels and report whether the docs list them in the same order as the view. The
            US rules require field lists in UI order.

      view_checks.py order EXTRACT_JSON --list 0 --modules 'hr_attendance*'

Views changed by inheritance (`<xpath>`) are flagged, because the final order on screen can
differ from the order in any single file. Confirm those in the browser.
"""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from dqr_common import (
    derived_field_label, emit, fail, find_docs_repo, find_source_repos, module_dirs,
    normalize_ws, python_field_labels, strip_trailing_ui_punct,
)


def view_files(mods):
    for repo_key, mod in mods:
        for xml in sorted(Path(mod).rglob('*.xml')):
            if 'tests' in xml.parts or 'i18n' in xml.parts or 'static' in xml.parts:
                continue
            yield repo_key, mod, xml


def parse(xml):
    try:
        return ET.parse(xml).getroot()
    except ET.ParseError:
        return None


def comparable(text):
    """Lowercase, single-spaced, with `&` read as `and` (headings often spell it out)."""
    return normalize_ws(text.replace('&', ' and ')).lower()


def docs_text(docs, paths):
    texts = {}
    for p in paths:
        path = Path(p)
        if not path.is_absolute():
            path = docs / path
        files = sorted(path.rglob('*.rst')) if path.is_dir() else [path]
        for f in files:
            raw = f.read_text(encoding='utf-8')
            key = str(f.relative_to(docs)) if f.resolve().is_relative_to(docs) else str(f)
            texts[key] = comparable(raw.replace('`', ' '))
    return texts


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------


def cmd_settings(args, docs, sources):
    mods = module_dirs(sources, args.modules)
    if not mods:
        fail(f'No modules match {args.modules}.')
    labels = python_field_labels(mods)
    texts = docs_text(docs, args.docs)

    items = []
    for repo_key, mod, xml in view_files(mods):
        root = parse(xml)
        if root is None:
            continue
        for elem in root.iter():
            if elem.tag not in ('setting', 'block'):
                continue
            # On <block>, `title` is the visible section title. On <setting>, `title` is only a
            # tooltip: the visible label is `string`, or the label of the inner field.
            label = elem.get('string') or (elem.get('title') if elem.tag == 'block' else None)
            source = 'attribute'
            if not label and elem.tag == 'setting':
                field = elem.find('.//field')
                if field is not None and field.get('name'):
                    fname = field.get('name')
                    known = labels.get(fname)
                    label = known[0]['label'] if known else derived_field_label(fname)
                    source = f'field `{fname}`'
            if not label:
                continue
            needle = comparable(strip_trailing_ui_punct(label))
            mentioned = [name for name, text in texts.items() if needle in text]
            items.append({
                'kind': 'section' if elem.tag == 'block' else 'setting',
                'label': label,
                'label_source': source,
                'module': mod.name,
                'location': f'{repo_key}:{xml.relative_to(mod.parent)}',
                'help': elem.get('help'),
                'mentioned_in': mentioned,
            })

    emit({
        'modules': [m.name for _, m in mods],
        'docs_searched': sorted(texts),
        'not_mentioned': [i for i in items if not i['mentioned_in']],
        'mentioned_count': sum(1 for i in items if i['mentioned_in']),
        'all': items,
    })


# ---------------------------------------------------------------------------
# order
# ---------------------------------------------------------------------------

LABEL_TAGS = {'field', 'setting', 'button', 'page', 'group', 'label', 'filter', 'block'}


def element_label(elem, labels):
    label = elem.get('string') or elem.get('title')
    if label:
        return label
    if elem.tag == 'field' and elem.get('name'):
        known = labels.get(elem.get('name'))
        return known[0]['label'] if known else derived_field_label(elem.get('name'))
    if elem.tag == 'setting':
        field = elem.find('.//field')
        if field is not None:
            return element_label(field, labels)
    return None


def cmd_order(args, docs, sources):
    data = json.loads(Path(args.extract_json).read_text())
    try:
        group = data['field_lists'][args.list]
    except IndexError:
        fail(f"The file has {len(data['field_lists'])} field lists; --list {args.list} is out of range.")
    wanted = [strip_trailing_ui_punct(i['label']) for i in group['items']]
    wanted_lc = [w.lower() for w in wanted]

    mods = module_dirs(sources, args.modules)
    if not mods:
        fail(f'No modules match {args.modules}.')
    labels = python_field_labels(mods)

    views = []
    for repo_key, mod, xml in view_files(mods):
        root = parse(xml)
        if root is None:
            continue
        for record in root.iter('record'):
            if record.get('model') != 'ir.ui.view':
                continue
            arch = next((f for f in record.findall('field') if f.get('name') == 'arch'), None)
            if arch is None:
                continue
            sequence = []
            for elem in arch.iter():
                if elem.tag in LABEL_TAGS:
                    label = element_label(elem, labels)
                    if label:
                        sequence.append(strip_trailing_ui_punct(label).lower())
            positions = {}
            for idx, label in enumerate(sequence):
                if label in wanted_lc and label not in positions:
                    positions[label] = idx
            if len(positions) < max(2, args.min_match):
                continue
            matched = [w for w in wanted_lc if w in positions]
            in_view_order = sorted(matched, key=lambda w: positions[w])
            views.append({
                'view_id': record.get('id'),
                'location': f'{repo_key}:{xml.relative_to(mod.parent)}',
                'inherits': any(f.get('name') == 'inherit_id' for f in record.findall('field')),
                'matched': len(matched),
                'of': len(wanted),
                'same_order': matched == in_view_order,
                'docs_order': [wanted[wanted_lc.index(w)] for w in matched],
                'view_order': [wanted[wanted_lc.index(w)] for w in in_view_order],
                'missing_from_view': [w for w in wanted if w.lower() not in positions],
            })

    views.sort(key=lambda v: (-v['matched'], v['inherits']))

    # Option lists often describe the values of a Python `selection=[(key, label), ...]`.
    selections = []
    for repo_key, mod in mods:
        for py in Path(mod).rglob('*.py'):
            if 'tests' in py.parts:
                continue
            text = py.read_text(encoding='utf-8', errors='replace')
            offsets = {}
            for label in wanted:
                pattern = r"""\(\s*['"][\w.]+['"]\s*,\s*(?:_\(\s*)?['"]""" + re.escape(label) + r"""['"]"""
                match = re.search(pattern, text)
                if match:
                    offsets[label] = match.start()
            if len(offsets) < 2:
                continue
            matched = [w for w in wanted if w in offsets]
            in_source = sorted(matched, key=offsets.get)
            selections.append({
                'location': f'{repo_key}:{py.relative_to(mod.parent)}:{text.count(chr(10), 0, min(offsets.values())) + 1}',
                'matched': len(matched),
                'of': len(wanted),
                'same_order': matched == in_source,
                'docs_order': matched,
                'source_order': in_source,
            })
    selections.sort(key=lambda s: -s['matched'])

    note = None
    if not views and not selections:
        note = ('No view or selection in these modules contains two or more of these labels. They may '
                'come from somewhere else (res.groups names, another module, JS). Check by hand.')
    emit({
        'file': data['file'],
        'note': note,
        'list_start_line': group['start_line'],
        'labels': wanted,
        'views': views[:args.limit],
        'selections': selections[:args.limit],
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--odoo')
    parser.add_argument('--enterprise')
    parser.add_argument('--docs-repo')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_set = sub.add_parser('settings')
    p_set.add_argument('--modules', nargs='+', required=True)
    p_set.add_argument('--docs', nargs='+', required=True, help='.rst files or folders to search')

    p_ord = sub.add_parser('order')
    p_ord.add_argument('extract_json')
    p_ord.add_argument('--list', type=int, default=0, help='Index into field_lists')
    p_ord.add_argument('--modules', nargs='+', required=True)
    p_ord.add_argument('--min-match', type=int, default=2)
    p_ord.add_argument('--limit', type=int, default=5)

    args = parser.parse_args()
    docs = find_docs_repo(args.docs_repo)
    if not docs:
        fail('Could not find the odoo/documentation repository. Pass --docs-repo.')
    sources = find_source_repos(docs, args.odoo, args.enterprise)
    if 'odoo' not in sources:
        fail('Could not find an odoo/odoo checkout. Pass --odoo or set ODOO_SRC.')
    {'settings': cmd_settings, 'order': cmd_order}[args.cmd](args, docs, sources)


if __name__ == '__main__':
    main()
