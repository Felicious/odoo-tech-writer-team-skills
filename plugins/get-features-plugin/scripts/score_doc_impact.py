#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
Score each PR's documentation impact from its diff (the output of
fetch_pr_files.py), and write one JSON object per PR to stdout:

  {"pr_number": 123, "modules": "sale", "doc_impact": "likely",
   "impact_reason": "labels, visibility", "matched_labels": "", "doc_pages": ""}

Levels, strongest first:
  confirmed  The PR removes or renames a UI label that the documentation shows
             as :guilabel: or :menuselection: (tier 2). doc_pages lists where.
  likely     The changed lines touch something users see (tier 1): labels and
             UI text, fields, buttons, menus, visibility, report content,
             data records (charts of accounts, taxes, states...), a new module.
  possible   A UI file changed but no specific signal was found (structure,
             styling), or an [IMP]/[ADD]/[REM]/[MOV] PR changed code.
  none       Only tests, translations, or code changes in fix/perf/refactor PRs.
  unknown    The PR's files couldn't be fetched or its diff can't be trusted
             (impact_reason says which).

Usage:
  score_doc_impact.py <pr_files.jsonl> [--docs-repo PATH [--docs-ref REF]] > pr_impact.jsonl

Without --docs-repo, tier 2 is skipped and nothing is scored "confirmed".
--docs-ref (default HEAD) is read with git grep, so the docs checkout's
current branch doesn't matter.

A one-line JSON summary is printed to stderr: prs, one count per level, and
docs_labels (the number of distinct labels indexed from the documentation) and
scorer_version.
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict

LEVELS = ["none", "unknown", "possible", "likely", "confirmed"]

# Bump whenever a rule change can move PRs between levels. Tracked lists
# (track_changes.py) then refresh impact columns without logging every
# re-scored PR as a change.
SCORER_VERSION = "2026-11-17"

# Labels found in more documentation pages than this are too generic
# ("Save", "Name", "Settings") to prove a page is affected.
GENERIC_LABEL_PAGES = 15

# Where each app's pages live in documentation/content, for module names whose
# first word doesn't already start a path segment there (sale -> sales/ works
# as is). An empty string means "no specific area" (framework modules).
DOC_AREAS = {
    "account": "accounting", "l10n": "fiscal_localizations", "stock": "inventory",
    "mrp": "manufacturing", "pos": "point_of_sale", "point": "point_of_sale",
    "website": "websites", "mail": "discuss", "im": "live_chat", "mass": "email_marketing",
    "event": "events", "survey": "surveys", "hr": "hr", "web": "", "base": "", "bus": "",
    "html": "", "portal": "", "auth": "", "resource": "", "product": "inventory",
    "uom": "inventory", "analytic": "accounting", "payment": "payment_providers",
    "delivery": "shipping", "quality": "quality", "repair": "repairs", "timesheet": "timesheets",
}
MAX_LISTED = 5

# Country pages in the docs (fiscal and payroll localizations), by the country
# code used in l10n_<code> module names. A country page only counts as affected
# when the PR touches that country's modules: "Electronic invoicing" removed
# from l10n_es must not match chile.rst.
COUNTRY_PAGES = {
    "ae": {"united_arab_emirates"}, "ar": {"argentina"}, "at": {"austria"}, "au": {"australia"},
    "be": {"belgium"}, "br": {"brazil"}, "ca": {"canada"}, "ch": {"switzerland"}, "cl": {"chile"},
    "co": {"colombia"}, "de": {"germany"}, "dk": {"denmark"}, "do": {"dominican_republic"},
    "ec": {"ecuador"}, "eg": {"egypt"}, "es": {"spain"}, "fr": {"france"}, "gt": {"guatemala"},
    "hk": {"hong_kong"}, "hr": {"croatia"}, "hu": {"hungary"}, "id": {"indonesia"}, "in": {"india"},
    "it": {"italy"}, "jo": {"jordan"}, "ke": {"kenya"}, "lu": {"luxembourg"}, "mx": {"mexico"},
    "my": {"malaysia"}, "nl": {"netherlands"}, "nz": {"new_zealand"}, "om": {"oman"}, "pe": {"peru"},
    "ph": {"philippines"}, "pl": {"poland"}, "ro": {"romania"}, "sa": {"saudi_arabia"},
    "sg": {"singapore"}, "th": {"thailand"}, "tr": {"turkey", "turkiye"}, "tw": {"taiwan"},
    "uk": {"united_kingdom"}, "gb": {"united_kingdom"}, "us": {"united_states"}, "uy": {"uruguay"},
    "uz": {"uzbekistan"}, "vn": {"vietnam"},
}
ALL_COUNTRY_PAGES = set().union(*COUNTRY_PAGES.values())
L10N_MODULE = re.compile(r"^l10n_([a-z]{2})(?:_|$)")

IGNORED_PATH = re.compile(r"(?:^|/)(?:tests?|i18n|i18n_extra)/|\.pot?$|(?:^|/)\.github/")
FEATURE_TAG = re.compile(r"^\s*\[(?:IMP|ADD|REM|MOV)\]", re.IGNORECASE)

# --- Tier 0: which files can affect the UI at all ---------------------------
UI_XML = re.compile(r"(?:^|/)(?:views|wizards?|report|static/src)/.+\.xml$")
MENU_DATA = re.compile(r"(?:^|/)data/[^/]*menu[^/]*\.xml$")
STYLE = re.compile(r"(?:^|/)static/src/.+\.s?css$")
FRONTEND_JS = re.compile(r"(?:^|/)static/src/.+\.js$")
SETTINGS = re.compile(r"res_config_settings[^/]*\.(?:py|xml)$")
# Records users see in the app: charts of accounts, taxes, fiscal positions,
# country states, mail templates... Demo data isn't shipped to users.
DATA_FILE = re.compile(r"(?:^|/)data/.+\.(?:csv|xml)$")

# --- Tier 1: what in the changed lines users see ----------------------------
# `<field name="...">` lines that define a view record, not a field shown in it.
RECORD_FIELDS = {
    "name", "model", "arch", "inherit_id", "priority", "mode", "type", "res_model",
    "view_mode", "view_id", "context", "domain", "key", "active", "sequence", "binding_model_id",
}
XML_LABEL_ATTR = re.compile(r'\b(?:string|placeholder|title|aria-label|confirm)="([^"]*[A-Za-z][^"]*)"')
XML_HELP_ATTR = re.compile(r'\bhelp="[^"]*[A-Za-z]')
XML_VIEW_FIELD = re.compile(r'<field\s+name="(\w+)"(?![^>]*\b(?:ref|eval)=)')
XML_CONTROL = re.compile(r"<(?:button|page|filter|menuitem)\b")
MENUITEM_NAME = re.compile(r'<menuitem\b[^>]*\bname="([^"]+)"')
XML_VISIBILITY = re.compile(r"\b(?:invisible|column_invisible|readonly|required|groups|optional)=")
XML_REPORT_VALUE = re.compile(r"\bt-(?:field|out|esc)=")
XML_TEXT_NODE = re.compile(r">\s*([^<>{}]*[A-Za-z][^<>{}]*?)\s*<")
XML_TEXT_LINE = re.compile(r"[A-Za-z][^<>={}]*")
PY_TEXT = re.compile(r"(?:^|[^\w])_(?:lt)?\(\s*[rf]?([\"'])(.+?)(?<!\\)\1")
PY_LABEL_ATTR = re.compile(r"\bstring=([\"'])(.+?)(?<!\\)\1")
PY_HELP_ATTR = re.compile(r"\bhelp=[\"']")
# ('draft', 'Draft') or ('draft', _lt('Draft')): the label starts with a capital,
# which rules out tuples of technical names like ('journal_id', 'currency_id').
PY_SELECTION = re.compile(r"\(\s*[\"'][\w.]+[\"']\s*,\s*(?:_lt?\()?\s*[\"']([A-Z][^\"']*)[\"']")
JS_TEXT = re.compile(r"(?:^|[^\w])_t\(\s*([\"'`])(.+?)(?<!\\)\1")


def changed_lines(patch):
    """Yield (sign, text) for each added or removed line of a unified diff."""
    for line in (patch or "").splitlines():
        if line[:1] in "+-" and not line.startswith(("+++", "---")):
            yield line[0], line[1:].strip()


def module_of(path):
    parts = path.split("/")
    if parts[0] == "addons" and len(parts) > 2:  # odoo/odoo: addons/<module>/...
        return parts[1]
    if parts[:2] == ["odoo", "addons"] and len(parts) > 3:  # odoo/odoo: odoo/addons/base/...
        return parts[2]
    if parts[0] not in ("odoo", "doc", "setup", "debian") and len(parts) > 1:  # odoo/enterprise
        return parts[0]
    return None


def scan_line(path, text):
    """Return (reasons, labels) for one changed line.

    Labels feed tier 2, so they only come from places that name things in the
    UI. Python messages (_("...")) count for tier 1 but aren't labels.
    """
    reasons, labels = set(), []
    if path.endswith(".xml"):
        labels += XML_LABEL_ATTR.findall(text) + MENUITEM_NAME.findall(text)
        if labels or XML_HELP_ATTR.search(text):
            reasons.add("labels")
        if XML_CONTROL.search(text):
            reasons.add("buttons/menus/filters")
        if XML_VISIBILITY.search(text):
            reasons.add("visibility")
        if XML_REPORT_VALUE.search(text) and "report" in path:
            reasons.add("report content")
        if any(name not in RECORD_FIELDS for name in XML_VIEW_FIELD.findall(text)):
            reasons.add("fields")
        nodes = XML_TEXT_NODE.findall(text)
        if not nodes and XML_TEXT_LINE.fullmatch(text) and " " in text:
            nodes = [text]  # a text node on its own line
        if nodes:
            reasons.add("UI text")
            labels += nodes
    elif path.endswith(".py"):
        texts = [m[1] for m in PY_TEXT.findall(text)]
        attrs = [m[1] for m in PY_LABEL_ATTR.findall(text)]
        options = PY_SELECTION.findall(text)
        if texts:
            reasons.add("UI text")
        if attrs or PY_HELP_ATTR.search(text):
            reasons.add("field labels")
        if options:
            reasons.add("selection options")
        labels += attrs + options
    elif path.endswith(".js"):
        texts = [m[1] for m in JS_TEXT.findall(text)]
        if texts:
            reasons.add("UI text")
            labels += texts
    return reasons, labels


def normalize(label):
    label = re.sub(r"\s+", " ", label).strip().strip(":.…").strip()
    return label.casefold()


def load_docs_labels(repo, ref):
    """Map each normalized :guilabel: / :menuselection: item to the pages that show it."""
    proc = subprocess.run(
        ["git", "-C", repo, "grep", "-o", "-E", r":(guilabel|menuselection):`[^`]+`", ref, "--", "content"],
        capture_output=True, text=True,
    )
    if proc.returncode not in (0, 1):
        sys.exit(f"git grep failed in {repo} at {ref}: {proc.stderr.strip()}")
    pages = defaultdict(set)
    for line in proc.stdout.splitlines():
        # Format: <ref>:<path>:<match>. Refs and .rst paths don't contain ':'.
        _, path, match = line.split(":", 2)
        role, _, value = match.partition(":`")
        items = value.rstrip("`").split("-->") if role == ":menuselection" else [value.rstrip("`")]
        for item in items:
            key = normalize(item)
            if len(key) >= 3:
                pages[key].add(path.removeprefix("content/"))
    return pages


def area_tokens(modules):
    """Docs path prefixes that belong to these modules' apps and countries."""
    tokens = set()
    for module in modules:
        first = module.split("_")[0]
        area = DOC_AREAS.get(first, first)
        if area:
            tokens.add(area)
        country = L10N_MODULE.match(module)
        if country:
            tokens |= COUNTRY_PAGES.get(country[1], set())
    return tokens


def page_segments(page):
    return page.removesuffix(".rst").split("/")


def in_area(page, tokens):
    return any(segment.startswith(token) for segment in page_segments(page) for token in tokens)


def other_country(page, tokens):
    """True if the page is about a country the PR doesn't touch."""
    countries = ALL_COUNTRY_PAGES.intersection(page_segments(page))
    return bool(countries) and not countries & tokens


def score_pr(pr, docs_pages):
    result = {"pr_number": pr["pr_number"], "scorer_version": SCORER_VERSION, "modules": "", "doc_impact": "unknown",
              "impact_reason": "", "matched_labels": "", "doc_pages": ""}
    if pr["files"] is None:
        result["impact_reason"] = pr.get("note", "")
        return result

    modules, reasons = [], []
    ui_files = code_files = False
    removed, added = Counter(), Counter()
    for f in pr["files"]:
        path = f["path"]
        if IGNORED_PATH.search(path):
            continue
        module = module_of(path)
        if module and module not in modules:
            modules.append(module)
        if path.endswith("__manifest__.py") and f["change"] == "added":
            reasons.append("new module")
        if SETTINGS.search(path) and "settings" not in reasons:
            reasons.append("settings")
        if STYLE.search(path):
            ui_files = True
            continue
        if UI_XML.search(path) or MENU_DATA.search(path) or FRONTEND_JS.search(path):
            ui_files = True
        if path.endswith((".py", ".js", ".xml")):
            code_files = True
        if DATA_FILE.search(path) and "demo" not in path and "data records" not in reasons:
            if f["change"] in ("added", "removed") or any(changed_lines(f.get("patch"))):
                reasons.append("data records")
        for sign, text in changed_lines(f.get("patch")):
            line_reasons, labels = scan_line(path, text)
            reasons += [r for r in sorted(line_reasons) if r not in reasons]
            (removed if sign == "-" else added).update(normalize(label) for label in labels)

    # Tier 2: labels this PR removes (not just moves) that the docs show. A
    # one-word label ("Signature") only counts on pages of the PR's own apps;
    # a longer one ("Use tabular form") is specific enough to count anywhere.
    tokens = area_tokens(modules)
    matched, pages = [], set()
    for label in (removed - added):
        all_pages = docs_pages.get(label, set())
        if not 0 < len(all_pages) <= GENERIC_LABEL_PAGES:
            continue
        label_pages = {page for page in all_pages if not other_country(page, tokens)}
        related = {page for page in label_pages if in_area(page, tokens)}
        if related or (" " in label and label_pages):
            matched.append(label)
            pages |= related or label_pages

    if matched:
        level = "confirmed"
    elif reasons:
        level = "likely"
    elif ui_files:
        level = "possible"
        reasons.append("UI files changed")
    elif code_files and FEATURE_TAG.search(pr.get("title") or ""):
        level = "possible"
        reasons.append("feature PR changes code")
    else:
        level = "none"

    result.update(
        modules=", ".join(modules),
        doc_impact=level,
        impact_reason=", ".join(reasons),
        matched_labels="; ".join(sorted(matched)[:MAX_LISTED]),
        doc_pages="; ".join(sorted(pages)[:MAX_LISTED]) + (f" (+{len(pages) - MAX_LISTED})" if len(pages) > MAX_LISTED else ""),
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pr_files", help="JSONL output of fetch_pr_files.py")
    parser.add_argument("--docs-repo", help="local clone of odoo/documentation")
    parser.add_argument("--docs-ref", default="HEAD", help="docs branch or ref to read, e.g. origin/saas-19.3")
    args = parser.parse_args()

    docs_pages = load_docs_labels(args.docs_repo, args.docs_ref) if args.docs_repo else {}

    counts = Counter()
    with open(args.pr_files) as f:
        for line in f:
            if line.strip():
                result = score_pr(json.loads(line), docs_pages)
                counts[result["doc_impact"]] += 1
                print(json.dumps(result))

    print(json.dumps({"prs": sum(counts.values()), **{level: counts[level] for level in reversed(LEVELS)},
                      "docs_labels": len(docs_pages), "scorer_version": SCORER_VERSION}), file=sys.stderr)


if __name__ == "__main__":
    main()
