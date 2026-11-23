#!/usr/bin/env python3
"""Run the automated checks from AGENTS.md (step 5) plus Vale, filtered by style scope.

Checks:
- lint         `python tests/main.py FILES` (the `make test` CI checks, scoped to the files)
- line_review  `REVIEW=1 python tests/main.py --max-line-length=100 FILES` (what `make review` runs)
- vale         Vale with the odoo-vale-linter styles. Results that contradict the file's scope
               are dropped (see references/vale-scope-filter.md)
- build        `make fast`, then keep warnings for FILES. Slow: only runs with --build

A missing tool is reported as `status: missing`, never skipped silently.

Usage:
    run_checks.py --scope-json SCOPES_JSON FILE [FILE ...] [--build] [--vale-config PATH]

SCOPES_JSON is the output of scope_for_path.py (path, or `-` to compute it from --ownership).
"""

import argparse
import json
import os
import shutil
from pathlib import Path

from dqr_common import emit, fail, find_docs_repo, run

YOU_WORDS = {'you', 'your', 'yours', "you're", 'youre'}

# Vale checks that encode a US-only rule, and checks that contradict a US Override.
NOT_US_DROP = {
    'Odoo.IconDescriptorFormatting': 'US-only format (parentheses inside :guilabel:); published '
                                     'guidelines put them outside.',
    'Odoo.ImageAlign': 'US-only rule; published guidelines allow :align:.',
}
US_NOTES = {
    'Odoo.FutureTense': 'US rules allow "will" when avoiding it forces awkward phrasing. Judge it.',
}


def python_for(docs):
    venv = docs / '.venv' / 'bin' / 'python'
    return str(venv) if venv.is_file() else shutil.which('python3') or 'python3'


def tail(text, limit=6000):
    return text if len(text) <= limit else '…\n' + text[-limit:]


def lint(docs, py, files, review=False):
    env = dict(os.environ)
    cmd = [py, 'tests/main.py']
    if review:
        env['REVIEW'] = '1'
        cmd.append('--max-line-length=100')
    proc = run(cmd + files, cwd=docs, env=env)
    output = (proc.stdout + proc.stderr).strip()
    if 'ModuleNotFoundError' in output:
        return {'status': 'missing', 'command': ' '.join(cmd + files), 'output': tail(output),
                'fix': 'Create the docs venv: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt'}
    findings = [line for line in output.splitlines() if line.startswith('content/') or ':' in line]
    return {
        'status': 'pass' if proc.returncode == 0 else 'issues',
        'command': ('REVIEW=1 ' if review else '') + ' '.join(cmd + files),
        'findings': findings if proc.returncode else [],
        'output': tail(output) if proc.returncode and not findings else None,
    }


def find_vale_config(explicit, docs):
    candidates = [explicit, os.getenv('VALE_CONFIG'),
                  docs.parent / 'odoo-vale-linter' / '.vale.ini',
                  Path.home() / 'Documents' / 'odoo' / 'odoo-vale-linter' / '.vale.ini',
                  docs / '.vale.ini']
    for cand in candidates:
        if cand and Path(cand).expanduser().is_file():
            return Path(cand).expanduser()
    return None


def has_us_descriptor(path, alert):
    """True when the flagged icon is followed by a US-format descriptor, :guilabel:`(name)`."""
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines()
        line = lines[alert['Line'] - 1]
        end = alert['Span'][1]
    except (OSError, IndexError, KeyError, TypeError):
        return False
    import re
    return bool(re.match(r'(?:\s*:icon:`[^`]+`)*\s*\*{0,2}:guilabel:`\(', line[end:]))


def vale(docs, files, scopes, config):
    exe = shutil.which('vale')
    if not exe:
        return {'status': 'missing', 'fix': 'Install Vale (odoo-writer-setup installs it).'}
    if not config:
        return {'status': 'missing', 'fix': 'odoo-vale-linter/.vale.ini not found. Pass --vale-config.'}
    proc = run([exe, '--config', str(config), '--output=JSON', *files], cwd=docs)
    try:
        data = json.loads(proc.stdout or '{}')
    except ValueError:
        return {'status': 'error', 'output': tail(proc.stdout + proc.stderr)}

    kept, dropped = [], []
    for path, alerts in data.items():
        resolved = (docs / path).resolve()
        rel = str(resolved.relative_to(docs)) if resolved.is_relative_to(docs) else path
        scope = scopes.get(rel, 'UNLISTED')
        for a in alerts:
            item = {
                'file': rel, 'line': a.get('Line'), 'check': a.get('Check'),
                'severity': a.get('Severity'), 'message': a.get('Message'), 'match': a.get('Match'),
            }
            check = item['check']
            reason = None
            us_descriptor = check == 'Odoo.MissingIconDescriptor' and has_us_descriptor(resolved, a)
            if scope == 'US' and check == 'Odoo.Pronouns' and (item['match'] or '').lower() in YOU_WORDS:
                reason = 'US Override: addressing the reader as "you" is allowed.'
            elif us_descriptor and scope == 'US':
                reason = ('False positive: the icon has a descriptor in the US format '
                          '(:guilabel:`(name)`), which this Vale rule does not recognize.')
            elif us_descriptor:
                item['note'] = ('The descriptor exists but uses the US format :guilabel:`(name)`. '
                                'Published format: (:guilabel:`name`).')
            elif scope == 'NOT_US' and check in NOT_US_DROP:
                reason = NOT_US_DROP[check]
            if reason:
                dropped.append({**item, 'reason': reason})
                continue
            if scope == 'US' and check in US_NOTES:
                item['note'] = US_NOTES[check]
            if scope in ('UNDECIDED', 'UNLISTED') and (check in NOT_US_DROP or check == 'Odoo.Pronouns'):
                item['note'] = 'Depends on the style scope, which is undecided for this file.'
            kept.append(item)
    return {
        'status': 'pass' if not kept else 'issues',
        'config': str(config),
        'findings': kept,
        'dropped_for_scope': dropped,
    }


def build(docs, files):
    env = dict(os.environ)
    venv_bin = docs / '.venv' / 'bin'
    if venv_bin.is_dir():
        env['PATH'] = f'{venv_bin}{os.pathsep}{env.get("PATH", "")}'
        env['VIRTUAL_ENV'] = str(docs / '.venv')
    if not shutil.which('sphinx-build', path=env['PATH']):
        return {'status': 'missing', 'fix': 'sphinx-build not found. Install requirements.txt in the docs venv.'}
    proc = run(['make', 'fast'], cwd=docs, env=env)
    output = proc.stdout + proc.stderr
    stems = [f[:-4] if f.endswith('.rst') else f for f in files]
    relevant = [
        line for line in output.splitlines()
        if ('WARNING' in line or 'ERROR' in line) and any(stem in line for stem in stems)
    ]
    return {
        'status': 'pass' if proc.returncode == 0 and not relevant else 'issues',
        'returncode': proc.returncode,
        'warnings_for_files': relevant,
        'output': tail(output) if proc.returncode else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('files', nargs='+')
    parser.add_argument('--scope-json', help='Output of scope_for_path.py')
    parser.add_argument('--ownership', help='agents/docs_ownership.md, if --scope-json is not given')
    parser.add_argument('--vale-config')
    parser.add_argument('--build', action='store_true', help='Also run `make fast` (slow)')
    parser.add_argument('--docs-repo')
    args = parser.parse_args()

    docs = find_docs_repo(args.docs_repo or args.files[0])
    if not docs:
        fail('Could not find the odoo/documentation repository. Pass --docs-repo.')
    files = []
    for f in args.files:
        p = Path(f).resolve()
        files.append(str(p.relative_to(docs)) if p.is_relative_to(docs) else f)

    if args.scope_json:
        scope_list = json.loads(Path(args.scope_json).read_text())
    elif args.ownership:
        from scope_for_path import load_rules, scope_for
        rules = load_rules(args.ownership)
        scope_list = [{'file': f, **scope_for(f, rules)} for f in files]
    else:
        scope_list = []
    scopes = {s['file']: s['scope'] for s in scope_list}

    py = python_for(docs)
    result = {
        'files': files,
        'scopes': scopes,
        'lint': lint(docs, py, files),
        'line_review': lint(docs, py, files, review=True),
        'vale': vale(docs, files, scopes, find_vale_config(args.vale_config, docs)),
        'build': build(docs, files) if args.build else {
            'status': 'not_run', 'note': 'Run with --build (slow), or run `make fast` in the background.',
        },
    }
    emit(result)


if __name__ == '__main__':
    main()
