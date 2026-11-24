#!/usr/bin/env python3
"""Locate the style rule files the review must follow.

The agent instructions (`AGENTS.md`, `agents/*.md`) come from odoo/documentation#21055. Until that
PR is merged they are not in a normal checkout, so this script looks for them in order:

1. The local docs checkout.
2. The docs base branch on GitHub (`odoo/documentation@<version>`), for when the PR is merged but
   the local checkout is not up to date.
3. The head branch of the PR, for when it is still open. The output then carries a warning.

The published guidelines (`content_guidelines.rst`, `rst_guidelines.rst`) are always read from
the local checkout.

Usage:
    get_rules.py [--docs-repo PATH] [--pr 21055] [--cache-dir DIR]

Prints JSON: {source, warning, files: {name: path}, published: {name: path}}.
"""

import argparse
import base64
import json
import tempfile
from pathlib import Path

from dqr_common import docs_version, emit, fail, find_docs_repo, run

AGENT_FILES = [
    'AGENTS.md',
    'agents/style_rules.md',
    'agents/docs_ownership.md',
    'agents/pr_checklist.md',
    'agents/pr_description.md',
]
PUBLISHED = [
    'content/contributing/documentation/content_guidelines.rst',
    'content/contributing/documentation/rst_guidelines.rst',
]
UPSTREAM = 'odoo/documentation'


def gh_fetch(repo, ref, path):
    """Return file contents from GitHub via `gh api`, or None."""
    proc = run(['gh', 'api', f'repos/{repo}/contents/{path}?ref={ref}'])
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads(proc.stdout)
        return base64.b64decode(payload['content']).decode('utf-8')
    except (ValueError, KeyError):
        return None


def fetch_all(repo, ref, cache):
    """Fetch every agent file from repo@ref into `cache`. Return {name: path} or None."""
    files = {}
    for name in AGENT_FILES:
        content = gh_fetch(repo, ref, name)
        if content is None:
            return None
        target = cache / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        files[name] = str(target)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--docs-repo')
    parser.add_argument('--pr', default='21055', help='PR that adds the agent rule files')
    parser.add_argument('--cache-dir', help='Where fetched files go (default: system temp dir)')
    args = parser.parse_args()

    docs = find_docs_repo(args.docs_repo)
    if not docs:
        fail('Could not find the odoo/documentation repository. Pass --docs-repo.')

    published = {Path(p).name: str(docs / p) for p in PUBLISHED if (docs / p).is_file()}
    missing_published = [p for p in PUBLISHED if not (docs / p).is_file()]

    # 1. Local checkout.
    if all((docs / name).is_file() for name in AGENT_FILES):
        emit({
            'source': 'local checkout',
            'warning': None,
            'files': {name: str(docs / name) for name in AGENT_FILES},
            'published': published,
            'missing_published': missing_published,
        })
        return

    cache = Path(args.cache_dir or Path(tempfile.gettempdir()) / 'doc-quality-review-rules')
    if run(['gh', '--version']).returncode != 0:
        fail(
            'The agent rule files are not in the local checkout, and the GitHub CLI (`gh`) is '
            'not available to fetch them. Pull the docs base branch, or install and log in to gh.',
            published=published,
        )

    # 2. Base branch upstream (PR already merged).
    version = docs_version(docs)
    if version:
        files = fetch_all(UPSTREAM, version, cache / f'base-{version}')
        if files:
            emit({
                'source': f'{UPSTREAM}@{version} (GitHub)',
                'warning': (
                    'The rule files are merged upstream but missing from your local checkout. '
                    'Rebase or pull your branch on the base branch to get them.'
                ),
                'files': files,
                'published': published,
                'missing_published': missing_published,
            })
            return

    # 3. Open PR head branch.
    proc = run([
        'gh', 'pr', 'view', args.pr, '--repo', UPSTREAM,
        '--json', 'state,headRefName,headRepository,headRepositoryOwner,url',
    ])
    if proc.returncode != 0:
        fail(f'Could not read PR #{args.pr}: {proc.stderr.strip()}', published=published)
    pr = json.loads(proc.stdout)
    head_repo = f"{pr['headRepositoryOwner']['login']}/{pr['headRepository']['name']}"
    files = fetch_all(head_repo, pr['headRefName'], cache / f"pr-{args.pr}")
    if not files:
        fail(
            f"Could not fetch the rule files from {head_repo}@{pr['headRefName']}.",
            published=published,
        )
    emit({
        'source': f"PR #{args.pr} ({pr['state'].lower()}) {head_repo}@{pr['headRefName']}",
        'warning': (
            f"These rules come from PR #{args.pr} ({pr['url']}), which is {pr['state'].lower()} "
            'and not merged into the base branch yet. They can still change.'
        ),
        'files': files,
        'published': published,
        'missing_published': missing_published,
    })


if __name__ == '__main__':
    main()
