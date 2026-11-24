#!/usr/bin/env python3
"""Check that an Odoo instance matches the docs branch before the browser check.

Reads the server version from `/web/webclient/version_info` (no login needed) and compares it with
the docs version in conf.py. AGENTS.md requires the instance to run the same version as the target
branch.

Usage:
    instance_info.py URL [--docs-repo PATH]
"""

import argparse
import json
import urllib.error
import urllib.request

from dqr_common import docs_version, emit, fail, find_docs_repo


def normalize(version):
    """`saas~19.4` / `saas-19.4` / `19.4` -> `19.4`; `20.0+e` / `20.0` -> `20.0`."""
    v = str(version).replace('saas~', '').replace('saas-', '')
    return v.split('+')[0].split('-')[0].strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('url')
    parser.add_argument('--docs-repo')
    args = parser.parse_args()

    base = args.url.rstrip('/')
    if base.endswith('/odoo') or base.endswith('/web'):
        base = base.rsplit('/', 1)[0]
    req = urllib.request.Request(
        base + '/web/webclient/version_info',
        data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': {}}).encode(),
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        fail(f'Could not reach {base}: {exc}. Is the instance running?')

    info = payload.get('result') or {}
    server = info.get('server_serie') or info.get('server_version')
    docs = find_docs_repo(args.docs_repo)
    expected = docs_version(docs) if docs else None
    emit({
        'url': base,
        'server_version': info.get('server_version'),
        'server_serie': info.get('server_serie'),
        'docs_version': expected,
        'version_match': bool(server and expected and normalize(server) == normalize(expected)),
        'is_localhost': any(h in base for h in ('localhost', '127.0.0.1', '0.0.0.0')),
    })


if __name__ == '__main__':
    main()
