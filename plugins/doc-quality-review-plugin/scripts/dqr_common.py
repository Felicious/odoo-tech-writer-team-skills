"""Shared helpers for the doc-quality-review scripts.

Standard library only. Every script imports this module from its own directory.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def emit(data):
    """Print JSON to stdout."""
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write('\n')


def fail(message, **extra):
    """Print a JSON error and exit with status 2."""
    emit({'error': message, **extra})
    sys.exit(2)


# ---------------------------------------------------------------------------
# Git and repository discovery
# ---------------------------------------------------------------------------


def run(cmd, cwd=None, env=None, check=False):
    """Run a command and return a CompletedProcess with text output."""
    return subprocess.run(
        cmd, cwd=cwd, env=env, check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def git(repo, *args):
    """Run git in `repo` and return stdout, or None on failure."""
    proc = run(['git', '-C', str(repo), *args])
    return proc.stdout if proc.returncode == 0 else None


def find_docs_repo(start=None):
    """Walk up from `start` (default: cwd) to the odoo/documentation repository root."""
    path = Path(start or os.getcwd()).resolve()
    if path.is_file():
        path = path.parent
    for candidate in [path, *path.parents]:
        if (candidate / 'conf.py').is_file() and (candidate / 'content').is_dir():
            return candidate
    return None


def docs_version(docs_repo):
    """Return the docs version from conf.py (for example `20.0` or `saas-19.4`)."""
    text = (Path(docs_repo) / 'conf.py').read_text(encoding='utf-8')
    match = re.search(r"^(?:version\s*=\s*)?release\s*=\s*['\"]([^'\"]+)['\"]", text, re.M)
    if not match:
        match = re.search(r"^version\s*=\s*['\"]([^'\"]+)['\"]", text, re.M)
    return match.group(1) if match else None


def current_branch(repo):
    out = git(repo, 'branch', '--show-current')
    return out.strip() if out else None


def _is_odoo_community(path):
    return (path / 'odoo-bin').is_file() and (path / 'addons').is_dir()


def _is_odoo_enterprise(path):
    return path.is_dir() and (path / 'web_studio').is_dir()


def find_source_repos(docs_repo, odoo=None, enterprise=None):
    """Locate the odoo/odoo and odoo/enterprise checkouts.

    Explicit paths win. Otherwise look for siblings of the docs repository, then for the
    `ODOO_SRC` / `ODOO_ENTERPRISE` environment variables.
    """
    parent = Path(docs_repo).resolve().parent
    found = {}

    odoo_candidates = [odoo, os.getenv('ODOO_SRC')] if odoo else [os.getenv('ODOO_SRC')]
    odoo_candidates += [parent / name for name in ('odoo-src', 'odoo', 'community', 'odoo-community')]
    for cand in odoo_candidates:
        if cand and _is_odoo_community(Path(cand).expanduser()):
            found['odoo'] = Path(cand).expanduser().resolve()
            break

    ent_candidates = [enterprise, os.getenv('ODOO_ENTERPRISE')] if enterprise else [os.getenv('ODOO_ENTERPRISE')]
    ent_candidates += [parent / 'enterprise', parent / 'odoo-enterprise']
    for cand in ent_candidates:
        if cand and _is_odoo_enterprise(Path(cand).expanduser()):
            found['enterprise'] = Path(cand).expanduser().resolve()
            break

    return found


def repo_info(docs_repo, sources):
    """Version and branch information used to warn about mismatched checkouts."""
    info = {
        'docs': {
            'path': str(docs_repo),
            'branch': current_branch(docs_repo),
            'conf_version': docs_version(docs_repo),
        },
    }
    for key, path in sources.items():
        info[key] = {'path': str(path), 'branch': current_branch(path)}
    expected = info['docs']['conf_version']
    mismatches = [
        f"{key} is on `{data['branch']}`, docs conf.py says `{expected}`"
        for key, data in info.items()
        if key != 'docs' and data['branch'] != expected
    ]
    info['version_mismatch'] = mismatches
    return info


def module_of(repo_key, rel_path):
    """Return the Odoo module name for a path relative to a source repository."""
    parts = Path(rel_path).parts
    if repo_key == 'odoo':
        if len(parts) > 1 and parts[0] == 'addons':
            return parts[1]
        if len(parts) > 2 and parts[:2] == ('odoo', 'addons'):
            return parts[2]
        return None
    return parts[0] if parts else None


def module_dirs(sources, patterns):
    """Resolve module name patterns (`hr_attendance`, `hr_attendance*`) to directories."""
    import fnmatch

    dirs = []
    roots = []
    if 'odoo' in sources:
        roots += [('odoo', sources['odoo'] / 'addons'), ('odoo', sources['odoo'] / 'odoo' / 'addons')]
    if 'enterprise' in sources:
        roots.append(('enterprise', sources['enterprise']))
    for repo_key, root in roots:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not (child / '__manifest__.py').is_file():
                continue
            if any(fnmatch.fnmatch(child.name, pat) for pat in patterns):
                dirs.append((repo_key, child))
    return dirs


# ---------------------------------------------------------------------------
# Odoo source helpers
# ---------------------------------------------------------------------------

_SIMPLE_FIELD_TYPES = {
    'Char', 'Text', 'Html', 'Boolean', 'Integer', 'Float', 'Monetary', 'Date', 'Datetime',
    'Binary', 'Image', 'Json', 'Properties',
}
_FIELD_DEF = re.compile(r'^\s+(\w+)\s*=\s*fields\.(\w+)\(', re.M)
_STRING_KW = re.compile(r"""\bstring\s*=\s*(?:_\(\s*)?(['"])(.+?)\1""", re.S)
_STR_LITERAL = re.compile(r"""\s*(?:_\(\s*)?(['"])(.*?)\1""")


def derived_field_label(name):
    """Reproduce Odoo's default field label (odoo/orm/fields.py)."""
    base = name[:-4] if name.endswith('_ids') else name[:-3] if name.endswith('_id') else name
    return base.replace('_', ' ').title()


def python_field_labels(module_paths):
    """Map field name -> list of {label, file, line, explicit} for every fields.X() definition."""
    labels = {}
    for _repo_key, mod in module_paths:
        for py in Path(mod).rglob('*.py'):
            if 'tests' in py.parts:
                continue
            try:
                text = py.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                continue
            for match in _FIELD_DEF.finditer(text):
                name, ftype = match.group(1), match.group(2)
                window = text[match.end():match.end() + 600]
                # Stop at the next field definition so we don't read a neighbour's string=.
                nxt = _FIELD_DEF.search(window)
                if nxt:
                    window = window[:nxt.start()]
                label = None
                kw = _STRING_KW.search(window)
                if kw:
                    label = kw.group(2)
                elif ftype in _SIMPLE_FIELD_TYPES:
                    lit = _STR_LITERAL.match(window)
                    if lit:
                        label = lit.group(2)
                elif ftype == 'Many2one':
                    lits = re.findall(r"""^\s*(['"])([^'"]+)\1\s*,\s*(?:_\(\s*)?(['"])([^'"]+)\3""", window)
                    if lits:
                        label = lits[0][3]
                explicit = label is not None
                related = 'related=' in window
                if label is None:
                    if related:
                        continue  # Related fields inherit the label of their target field.
                    label = derived_field_label(name)
                line = text.count('\n', 0, match.start()) + 1
                labels.setdefault(name, []).append({
                    'label': label, 'file': str(py), 'line': line, 'explicit': explicit,
                })
    return labels


# ---------------------------------------------------------------------------
# RST helpers
# ---------------------------------------------------------------------------


def normalize_ws(text):
    return re.sub(r'\s+', ' ', text).strip()


def line_of(text, offset):
    return text.count('\n', 0, offset) + 1


def strip_trailing_ui_punct(label):
    """Labels in the docs drop trailing ellipses and end punctuation copied from the UI."""
    return re.sub(r'[\s.…:!?]+$', '', label)
