#!/usr/bin/env python3
"""Check UI labels, menu paths, and cross-references from extract_refs.py against the sources.

- Labels: searched in odoo/odoo and odoo/enterprise (*.py, *.xml, *.js). Each label gets a status:
    found          exact case, as a quoted string or element text
    weak           exact case, but only inside a longer string (may be a coincidence)
    found_derived  no literal string, but a field whose default label matches (`scheduled_date`)
    case_mismatch  only found with different capitalization (the docs must match the UI exactly)
    not_found      nowhere in the source; check in the UI or report it
  `generic: true` means the label is so common (Save, New) that a match proves little.
- Menu paths: rebuilt from every <menuitem> in both repositories. A trailing " app" on the first
  segment is removed first (US-scope menu path format).
- :ref: / :doc: targets: checked against anchors and files in the docs repository.

The source tells you a string exists. It does not prove where it shows up in the UI (inherited
views, conditional visibility). Use the browser check for that.

Usage:
    verify_ui_refs.py EXTRACT_JSON [--modules 'hr_attendance*' ...] [--odoo PATH] [--enterprise PATH]
"""

import argparse
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from dqr_common import emit, fail, find_docs_repo, find_source_repos, git, module_of, repo_info, run

CODE_GLOBS = ['*.py', '*.xml', '*.js']
GENERIC_THRESHOLD = 40


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


def grep(repo, pattern, ignore_case=False, fixed=True, globs=CODE_GLOBS):
    args = ['grep', '-n', '-I', '--no-color']
    if fixed:
        args.append('-F')
    else:
        args.append('-E')
    if ignore_case:
        args.append('-i')
    args += ['-e', pattern, '--', *globs]
    out = git(repo, *args)
    hits = []
    for raw in (out or '').splitlines():
        parts = raw.split(':', 2)
        if len(parts) == 3:
            hits.append({'file': parts[0], 'line': int(parts[1]), 'text': parts[2].strip()})
    return hits


def label_variants(label):
    """The label as written in the docs, plus its XML-escaped forms."""
    variants = {label, html.escape(label, quote=False), html.escape(label, quote=True)}
    return [v for v in variants if v]


def strong(hit_text, variant):
    """True when the variant is the whole string: quoted, or the full text of an XML element."""
    esc = re.escape(variant)
    trail = r'[\s.…:!?]*'
    return bool(re.search(
        rf'(["\'`]{esc}{trail}["\'`])|(>\s*{esc}{trail}\s*<)|(>\s*{esc}{trail}\s*$)|(^\s*{esc}{trail}\s*<)',
        hit_text,
    ))


def rank(hit, modules):
    score = 0
    if hit['strong']:
        score -= 100
    if modules and hit.get('module') in modules:
        score -= 50
    if '/tests/' in hit['file'] or '/i18n/' in hit['file']:
        score += 30
    return score


def search_label(label, sources, modules):
    hits = []
    for key, repo in sources.items():
        for variant in label_variants(label):
            for hit in grep(repo, variant):
                hit['repo'] = key
                hit['module'] = module_of(key, hit['file'])
                hit['strong'] = strong(hit['text'], variant)
                hits.append(hit)
    unique = {(h['repo'], h['file'], h['line']): h for h in hits}
    return sorted(unique.values(), key=lambda h: rank(h, modules))


def field_name_for(label):
    return re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_')


def check_label(label, sources, modules):
    hits = search_label(label, sources, modules)
    result = {'label': label}
    if any(h['strong'] for h in hits):
        result['status'] = 'found'
        result['generic'] = len(hits) > GENERIC_THRESHOLD
        result['hit_count'] = len(hits)
        result['in_modules'] = sorted({h['module'] for h in hits if h['module'] in modules}) if modules else None
        result['evidence'] = [_evidence(h, sources) for h in hits[:3]]
        return result

    # Case-insensitive: the docs must match UI capitalization exactly.
    ci = []
    for key, repo in sources.items():
        for hit in grep(repo, label, ignore_case=True):
            hit['repo'] = key
            hit['module'] = module_of(key, hit['file'])
            match = next((m for m in re.finditer(re.escape(label), hit['text'], re.I)
                          if m.group(0) != label and strong(hit['text'], m.group(0))), None)
            hit['source_spelling'] = match.group(0) if match else None
            hit['strong'] = bool(match)
            ci.append(hit)
    ci.sort(key=lambda h: rank(h, modules))
    if ci and any(h['strong'] for h in ci):
        result['status'] = 'case_mismatch'
        result['source_spelling'] = next(h['source_spelling'] for h in ci if h['strong'])
        result['evidence'] = [_evidence(h, sources) for h in ci[:3]]
        return result

    # Exact case, but only inside longer strings: may be a coincidence.
    if hits:
        result['status'] = 'weak'
        result['generic'] = len(hits) > GENERIC_THRESHOLD
        result['hit_count'] = len(hits)
        result['evidence'] = [_evidence(h, sources) for h in hits[:3]]
        return result

    # Field without string=: Odoo derives the label from the field name.
    fname = field_name_for(label)
    derived = []
    for candidate in (fname, fname + '_id', fname + '_ids'):
        for key, repo in sources.items():
            for hit in grep(repo, rf'^\s+{candidate}\s*=\s*fields\.', fixed=False, globs=['*.py']):
                hit['repo'] = key
                hit['module'] = module_of(key, hit['file'])
                hit['strong'] = True
                if 'string=' not in hit['text']:
                    derived.append(hit)
    if derived:
        derived.sort(key=lambda h: rank(h, modules))
        result['status'] = 'found_derived'
        result['evidence'] = [_evidence(h, sources) for h in derived[:3]]
        return result

    result['status'] = 'not_found'
    pot = []
    for key, repo in sources.items():
        for hit in grep(repo, f'msgid "{label}', globs=['*.pot']):
            hit['repo'] = key
            pot.append(hit)
    if pot:
        result['note'] = 'Only in translation templates (.pot), which can lag the code.'
        result['evidence'] = [_evidence(h, sources) for h in pot[:3]]
    return result


def _evidence(hit, sources):
    return {
        'location': f"{hit['repo']}:{hit['file']}:{hit['line']}",
        'abs_path': str(Path(sources[hit['repo']]) / hit['file']),
        'module': hit.get('module'),
        'text': hit['text'][:200],
    }


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------


def action_names(sources):
    """Map qualified action id -> name, for menuitems without a name attribute."""
    names = {}
    pattern = r'<record[^>]+model="ir\.actions\.(act_window|server|client|report|act_url)"'
    for key, repo in sources.items():
        out = git(repo, 'grep', '-n', '-I', '-E', '-A', '4', '-e', pattern, '--', '*.xml') or ''
        current = None
        for raw in out.splitlines():
            match = re.match(r'(.+?)[:-](\d+)[:-](.*)$', raw)
            if not match:
                current = None
                continue
            path, text = match.group(1), match.group(3)
            rec = re.search(r'<record[^>]*\bid="([^"]+)"', text)
            if rec:
                mod = module_of(key, path)
                rid = rec.group(1)
                current = rid if '.' in rid else f'{mod}.{rid}'
                continue
            name = re.search(r'<field name="name"[^>]*>([^<]+)</field>', text)
            if current and name:
                names.setdefault(current, html.unescape(name.group(1).strip()))
                current = None
    return names


def menu_index(sources):
    """Return (menus, children). menus: id -> {names:set, parent, action, location}."""
    menus = {}
    for key, repo in sources.items():
        files = (git(repo, 'grep', '-l', '-I', '-e', '<menuitem', '--', '*.xml') or '').split()
        for rel in files:
            if '/tests/' in rel:
                continue
            mod = module_of(key, rel)
            try:
                root = ET.parse(Path(repo) / rel).getroot()
            except ET.ParseError:
                continue

            def qualify(ref):
                return ref if not ref or '.' in ref else f'{mod}.{ref}'

            def walk(elem, enclosing):
                for child in elem:
                    if child.tag == 'menuitem':
                        mid = qualify(child.get('id'))
                        entry = menus.setdefault(mid, {
                            'names': set(), 'parent': None, 'action': None, 'locations': [],
                        })
                        if child.get('name'):
                            entry['names'].add(child.get('name'))
                        parent = qualify(child.get('parent')) or enclosing
                        if parent:
                            entry['parent'] = parent
                        if child.get('action'):
                            entry['action'] = qualify(child.get('action'))
                        entry['locations'].append(f'{key}:{rel}')
                        walk(child, mid)
                    else:
                        walk(child, enclosing)

            walk(root, None)

    actions = None
    for entry in menus.values():
        if not entry['names'] and entry['action']:
            if actions is None:
                actions = action_names(sources)
            if entry['action'] in actions:
                entry['names'].add(actions[entry['action']])

    children = {}
    for mid, entry in menus.items():
        children.setdefault(entry['parent'], []).append(mid)
    return menus, children


def check_menu(menu, menus, children):
    segments = menu['menu_segments']
    result = {
        'text': menu['text'], 'line': menu['line'], 'segments': segments,
        # US scope requires `<App> app -->`; Not US requires the bare app name.
        'starts_with_app_suffix': menu.get('starts_with_app_suffix'),
    }

    def named(ids, name, ignore_case=False):
        if ignore_case:
            return [m for m in ids if name.lower() in {n.lower() for n in menus[m]['names']}]
        return [m for m in ids if name in menus[m]['names']]

    frontier = named(children.get(None, []), segments[0])
    case_issue = False
    if not frontier:
        frontier = named(children.get(None, []), segments[0], ignore_case=True)
        case_issue = bool(frontier)
    if not frontier:
        result['status'] = 'app_not_found'
        result['root_menus_sample'] = sorted(
            {n for m in children.get(None, []) for n in menus[m]['names']}
        )[:80]
        return result

    matched = 1
    for seg in segments[1:]:
        kids = [k for m in frontier for k in children.get(m, [])]
        nxt = named(kids, seg)
        if not nxt:
            nxt = named(kids, seg, ignore_case=True)
            case_issue = case_issue or bool(nxt)
        if not nxt:
            result['status'] = 'partial'
            result['matched_segments'] = matched
            result['available_at_break'] = sorted({n for k in kids for n in menus[k]['names']})
            result['menu_ids'] = frontier[:5]
            return result
        frontier = nxt
        matched += 1

    result['status'] = 'case_mismatch' if case_issue else 'found'
    result['menu_ids'] = frontier[:5]
    result['locations'] = sorted({loc for m in frontier for loc in menus[m]['locations']})[:5]
    return result


# ---------------------------------------------------------------------------
# Cross-references
# ---------------------------------------------------------------------------


def check_links(data, docs):
    anchors = set()
    out = git(docs, 'grep', '-h', '-I', '-E', '-e', r'^\s*\.\. _[^:]+:\s*$', '--', 'content') or ''
    for raw in out.splitlines():
        match = re.match(r'\s*\.\. _([^:]+):', raw)
        if match:
            anchors.add(match.group(1).strip().lower())

    results = []
    for ref in data['refs']:
        ok = ref['target'].lower() in anchors
        results.append({'kind': 'ref', **ref, 'status': 'ok' if ok else 'missing_anchor'})

    page_dir = (docs / data['file']).parent
    for doc in data['docs']:
        target = doc['target']
        path = (docs / 'content' / target.lstrip('/')) if target.startswith('/') else (page_dir / target)
        ok = Path(str(path) + '.rst').is_file() or path.with_suffix('.rst').is_file()
        results.append({'kind': 'doc', **doc, 'status': 'ok' if ok else 'missing_page'})
    return results


# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('extract_json', help='Output of extract_refs.py (path, or - for stdin)')
    parser.add_argument('--modules', nargs='*', default=[], help='Module patterns to rank evidence')
    parser.add_argument('--odoo')
    parser.add_argument('--enterprise')
    parser.add_argument('--docs-repo')
    args = parser.parse_args()

    raw = Path('/dev/stdin').read_text() if args.extract_json == '-' else Path(args.extract_json).read_text()
    data = json.loads(raw)
    docs = find_docs_repo(args.docs_repo)
    if not docs:
        fail('Could not find the odoo/documentation repository. Pass --docs-repo.')
    sources = find_source_repos(docs, args.odoo, args.enterprise)
    if 'odoo' not in sources:
        fail('Could not find an odoo/odoo checkout. Pass --odoo or set ODOO_SRC.')

    import fnmatch
    module_names = set()
    if args.modules:
        for key, repo in sources.items():
            roots = [repo / 'addons', repo / 'odoo' / 'addons'] if key == 'odoo' else [repo]
            for root in roots:
                if root.is_dir():
                    module_names.update(
                        p.name for p in root.iterdir()
                        if any(fnmatch.fnmatch(p.name, pat) for pat in args.modules)
                    )

    labels = {}
    for item in data['guilabels']:
        labels.setdefault(item['compare_as'], []).append(item['line'])
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        label_results = list(pool.map(lambda lbl: check_label(lbl, sources, module_names), labels))
    for res in label_results:
        res['lines'] = labels[res['label']]

    menus, children = menu_index(sources) if data['menuselections'] else ({}, {})
    menu_results = [check_menu(m, menus, children) for m in data['menuselections']]

    summary = {}
    for res in label_results:
        summary[res['status']] = summary.get(res['status'], 0) + 1

    emit({
        'file': data['file'],
        'repos': repo_info(docs, sources),
        'modules_used_for_ranking': sorted(module_names),
        'label_summary': summary,
        'labels': label_results,
        'menus': menu_results,
        'links': check_links(data, docs),
    })


if __name__ == '__main__':
    main()
