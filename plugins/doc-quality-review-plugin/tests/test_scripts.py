#!/usr/bin/env python3
"""Tests for the doc-quality-review scripts.

Run: python3 plugins/doc-quality-review-plugin/tests/test_scripts.py

Tests that need the odoo/documentation, odoo/odoo, and odoo/enterprise checkouts, or Vale, are
skipped when those aren't found. Point to them with DOCS_REPO, ODOO_SRC, and ODOO_ENTERPRISE.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / 'scripts'
FIXTURES = HERE / 'fixtures'
sys.path.insert(0, str(SCRIPTS))

import dqr_common  # noqa: E402
import run_checks  # noqa: E402
import scope_for_path  # noqa: E402


def script(name, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / name), *map(str, args)],
        text=True, capture_output=True,
    )
    return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else None


def find_docs():
    for cand in (os.getenv('DOCS_REPO'), Path.home() / 'Documents' / 'odoo' / 'documentation'):
        if cand and dqr_common.find_docs_repo(cand):
            return dqr_common.find_docs_repo(cand)
    return None


DOCS = find_docs()
SOURCES = dqr_common.find_source_repos(DOCS) if DOCS else {}


class ScopeTests(unittest.TestCase):
    rules = scope_for_path.load_rules(FIXTURES / 'docs_ownership.md')

    def scope(self, path):
        return scope_for_path.scope_for(path, self.rules)['scope']

    def test_paths(self):
        expected = {
            'content/applications/hr/attendances.rst': 'US',
            'content/applications/hr/payroll.rst': 'US',
            'content/applications/hr.rst': 'US',
            'content/applications/productivity/knowledge.rst': 'US',
            'content/applications/productivity/ai/agents.rst': 'US',
            'content/applications/productivity/spreadsheet.rst': 'NOT_US',
            'content/applications/sales/crm/pipeline.rst': 'US',
            'content/applications/sales/point_of_sale.rst': 'NOT_US',
            'content/applications/finance/expenses.rst': 'US',
            'content/applications/finance/accounting/taxes.rst': 'NOT_US',
            'content/applications/studio.rst': 'NOT_US',
            'content/developer/reference.rst': 'NOT_US',
            'content/applications/essentials/property_fields.rst': 'UNDECIDED',
            'content/applications/general/users.rst': 'UNDECIDED',
            'content/applications/finance.rst': 'UNDECIDED',
            'content/applications/sales.rst': 'UNDECIDED',
            'content/applications/services.rst': 'UNDECIDED',
            'content/applications/nonexistent/page.rst': 'UNLISTED',
        }
        for path, scope in expected.items():
            with self.subTest(path=path):
                self.assertEqual(self.scope(path), scope)


class ExtractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        code, cls.data = script('extract_refs.py', FIXTURES / 'planted.rst')
        assert code == 0, cls.data

    def test_menus(self):
        menus = self.data['menuselections']
        self.assertEqual(len(menus), 2)
        self.assertTrue(menus[0]['starts_with_app_suffix'])
        self.assertEqual(menus[0]['menu_segments'], ['Attendances', 'Configuration', 'Settings'])

    def test_labels(self):
        compare = [g['compare_as'] for g in self.data['guilabels']]
        self.assertIn('trash', compare)  # parentheses of the icon descriptor removed
        self.assertIn('Device & Location Tracking', compare)

    def test_structure(self):
        self.assertEqual(len(self.data['field_lists'][0]['items']), 3)
        self.assertIsNotNone(self.data['meta'])
        self.assertEqual(self.data['images'][0]['align'], 'center')
        self.assertEqual(self.data['headings'][0]['text'], 'Attendances')
        self.assertEqual(self.data['icons'][0]['icon'], 'fa-trash-o')

    def test_italic_elements(self):
        found = [(i['label'], i['element']) for i in self.data['guilabel_for_italic_element']]
        self.assertEqual(found, [('Kiosk Settings', 'section')])

    def test_nested_field_lists(self):
        groups = self.data['field_lists']
        nested = next(g for g in groups if g['items'][0]['label'] == 'Validation')
        self.assertEqual([i['label'] for i in nested['items']], ['Validation', 'Check-Out', 'Tracking'])
        self.assertEqual(nested['items'][0]['description'], 'Select a mode:')
        inner = next(g for g in groups if g['items'][0]['label'] == 'Mode A')
        self.assertEqual(len(inner['items']), 2)


@unittest.skipUnless(DOCS and 'odoo' in SOURCES and 'enterprise' in SOURCES,
                     'docs, odoo, and enterprise checkouts needed')
class VerifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = Path(os.getenv('TMPDIR', '/tmp')) / 'dqr-tests'
        tmp.mkdir(parents=True, exist_ok=True)
        code, data = script('extract_refs.py', FIXTURES / 'planted.rst')
        (tmp / 'planted.json').write_text(json.dumps(data))
        code, cls.result = script('verify_ui_refs.py', tmp / 'planted.json',
                                  '--modules', 'hr_attendance*', '--docs-repo', DOCS)
        assert code == 0, cls.result

    def label(self, name):
        return next(item for item in self.result['labels'] if item['label'] == name)

    def test_labels(self):
        self.assertEqual(self.label('Automatic Check-Out')['status'], 'found')
        self.assertEqual(self.label('Device & Location Tracking')['status'], 'found')
        self.assertEqual(self.label('automatic check-out')['status'], 'case_mismatch')
        self.assertEqual(self.label('Frobnicate Timesheets Daily')['status'], 'not_found')

    def test_menus(self):
        statuses = [m['status'] for m in self.result['menus']]
        self.assertEqual(statuses, ['found', 'partial'])
        self.assertIn('Configuration', self.result['menus'][1]['available_at_break'])

    def test_links(self):
        self.assertEqual({l['status'] for l in self.result['links']}, {'missing_anchor', 'missing_page'})

    def test_settings_entities_decoded(self):
        code, data = script('view_checks.py', '--docs-repo', DOCS, 'settings',
                            '--modules', 'hr_attendance', '--docs', FIXTURES / 'planted.rst')
        labels = {i['label'] for i in data['all']}
        self.assertIn('Device & Location Tracking', labels)
        self.assertNotIn('Device &amp; Location Tracking', labels)


@unittest.skipUnless(DOCS and shutil.which('vale') and run_checks.find_vale_config(None, DOCS or Path('.')),
                     'vale and odoo-vale-linter needed')
class ValeFilterTests(unittest.TestCase):
    def run_scope(self, scope):
        path = str(FIXTURES / 'planted.rst')
        out = run_checks.vale(DOCS, [path], {path: scope}, run_checks.find_vale_config(None, DOCS))
        kept = {f['check'] for f in out['findings']}
        dropped = {f['check'] for f in out['dropped_for_scope']}
        return kept, dropped

    def test_us(self):
        kept, dropped = self.run_scope('US')
        self.assertIn('Odoo.Pronouns', dropped)
        self.assertIn('Odoo.MissingIconDescriptor', dropped)
        self.assertIn('Odoo.ImageAlign', kept)

    def test_not_us(self):
        kept, dropped = self.run_scope('NOT_US')
        self.assertIn('Odoo.Pronouns', kept)
        self.assertIn('Odoo.ImageAlign', dropped)


if __name__ == '__main__':
    unittest.main(verbosity=2)
