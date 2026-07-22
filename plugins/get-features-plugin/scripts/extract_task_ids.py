#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl"]
# ///
"""
Extract task IDs from locally-saved PR JSONL files (one JSON object per line,
each containing at least: number, title, url, body, state, author, created_at,
merged_at), optionally filter the rows, and write a CSV (stdout) and/or a
clickable XLSX report.

Usage:
  extract_task_ids.py [options] <input.jsonl> [<input2.jsonl> ...] > output.csv

Options:
  --json                    Write JSON to stdout instead of CSV.
  --exclude-author LOGIN    Drop PRs by this author (repeatable, e.g. fw-bot).
  --require-task            Drop PRs with no extractable task ID.
  --exclude-csv PATH        Drop PRs whose task ID appears in this CSV.
  --exclude-column NAME     Column of --exclude-csv holding task IDs or task
                            URLs (default: "RD Task ID").
  --xlsx PATH               Also write a clickable spreadsheet report.
  --impact-jsonl PATH       Per-PR documentation impact (from score_doc_impact.py).
                            Adds the modules, doc_impact, impact_reason,
                            matched_labels and doc_pages columns.
  --doc-impact MODE         With --impact-jsonl: "keep" drops tasks scored
                            "none", "drop" drops tasks scored possible, likely
                            or confirmed, "label" (default) filters nothing.
                            A task takes the strongest level of its PRs.

Every row also gets three type columns, read from the PR title's leading
[TAG]: tag (FIX, IMP, REF...; OTHER if unrecognized, empty if absent),
change_type (feature, fix, technical or other) and task_type (the task's
strongest change_type across its PRs: feature > fix > technical > other).

A one-line JSON summary of the filtering is printed to stderr.
"""
import argparse
import csv
import json
import re
import sys

DEFAULT_PROJECT_ID = "19060"

TASK_URL_PATTERN = re.compile(r"odoo\.com/odoo/(?:project/)?(\d+)/tasks/(\d+)", re.IGNORECASE)
PROJECT_TASK_URL_PATTERN = re.compile(r"odoo\.com/odoo/(?:project\.task|all-tasks|my-tasks)/(\d+)", re.IGNORECASE)

PATTERNS = [
    re.compile(r"task-id-(\d+)", re.IGNORECASE),
    re.compile(r"taskid\s*[-:]\s*(\d+)", re.IGNORECASE),
    re.compile(r"task\s*[-~]\s*(\d+)", re.IGNORECASE),
    re.compile(r"task\s*:\s*\[?(\d+)", re.IGNORECASE),
    re.compile(r"task\s+id\s*:?\s*\[?(\d+)", re.IGNORECASE),
    re.compile(r"opw\s*[-:]?\s*\[?(\d+)", re.IGNORECASE),
]

CSV_FIELDS = [
    "pr_number", "state", "author", "created_at", "merged_at",
    "tag", "change_type", "title", "pr_url", "task_id", "task_type", "task_url",
]
XLSX_FIELDS = [
    "task_id", "task_url", "task_type", "pr_number", "pr_url", "tag", "change_type", "title",
    "state", "author", "created_at",
]
XLSX_WIDTHS = {
    "task_id": 10, "task_url": 48, "task_type": 11, "pr_number": 10, "pr_url": 42, "tag": 8,
    "change_type": 13, "title": 70, "state": 8, "author": 18, "created_at": 21,
}

# Title tags, from Odoo's commit message guidelines plus variants seen in PR
# titles. Markers like [WIP], [DRAFT] or [FW] are skipped to reach the real tag.
CHANGE_TYPES = {
    "IMP": "feature", "ADD": "feature", "REM": "feature", "MOV": "feature",
    "FIX": "fix", "REV": "fix", "SEC": "fix",
    "REF": "technical", "PERF": "technical", "CLN": "technical", "LINT": "technical",
    "I18N": "technical", "MERGE": "technical", "CLA": "technical", "REL": "technical",
    "POC": "technical",
}
TAG_ALIASES = {"IMPR": "IMP", "NEW": "ADD", "CLEAN": "CLN", "REVERT": "REV", "PERFORMANCE": "PERF"}
TAG_MARKERS = {"WIP", "DRAFT", "FW", "FWD"}
VERSION_MARKER = re.compile(r"(?:SAAS-?)?\d+(?:\.\d+)?")  # [18.0], [saas-17.4]
# Weakest to strongest, for a task's type across its PRs.
TASK_TYPE_ORDER = ["other", "technical", "fix", "feature"]
LEADING_BRACKETS = re.compile(r"\s*((?:\[[^\]]*\]\s*)+)")
IMPACT_FIELDS = ["modules", "doc_impact", "impact_reason", "matched_labels", "doc_pages"]
IMPACT_WIDTHS = {"modules": 24, "doc_impact": 11, "impact_reason": 34, "matched_labels": 30, "doc_pages": 50}
# Weakest to strongest; must match score_doc_impact.py.
IMPACT_LEVELS = ["none", "unknown", "possible", "likely", "confirmed"]
HAS_IMPACT = {"possible", "likely", "confirmed"}

# Which URL each clickable column links to.
XLSX_LINKS = {"task_id": "task_url", "task_url": "task_url", "pr_number": "pr_url", "pr_url": "pr_url"}


def extract_task_info(body):
    body = body or ""
    url_match = TASK_URL_PATTERN.search(body)
    if url_match:
        project_id, task_id = url_match.group(1), url_match.group(2)
        return task_id, project_id
    project_task_match = PROJECT_TASK_URL_PATTERN.search(body)
    if project_task_match:
        return project_task_match.group(1), DEFAULT_PROJECT_ID
    for pattern in PATTERNS:
        match = pattern.search(body)
        if match:
            return match.group(1), DEFAULT_PROJECT_ID
    return None, None


def tag_of(title):
    """The PR title's tag: FIX, IMP... OTHER if unrecognized, "" if there is none."""
    match = LEADING_BRACKETS.match(title or "")
    if not match:
        return ""
    for group in re.findall(r"\[([^\]]*)\]", match.group(1)):
        for token in re.split(r"[\s/,+&]+", group.upper()):
            token = TAG_ALIASES.get(token, token)
            if token in CHANGE_TYPES:
                return token
            if token and token not in TAG_MARKERS and not VERSION_MARKER.fullmatch(token):
                return "OTHER"  # e.g. "[Pie chart] ..." or "[Sign] ..."
    return "OTHER"


def add_task_types(rows):
    """Set each row's task_type: the strongest change_type among its task's PRs."""
    strongest = {}
    for r in rows:
        if r["task_id"]:
            current = strongest.get(r["task_id"], "other")
            strongest[r["task_id"]] = max(current, r["change_type"], key=TASK_TYPE_ORDER.index)
    for r in rows:
        r["task_type"] = strongest.get(r["task_id"], r["change_type"])
    return strongest


def process(paths):
    results = []
    for path in paths:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                pr = json.loads(line)
                task_id, project_id = extract_task_info(pr.get("body", ""))
                task_url = (
                    f"https://www.odoo.com/odoo/project/{project_id}/tasks/{task_id}"
                    if task_id else None
                )
                tag = tag_of(pr.get("title"))
                results.append({
                    "tag": tag,
                    "change_type": CHANGE_TYPES.get(tag, "other"),
                    "pr_number": pr.get("number"),
                    "state": pr.get("state"),
                    "author": pr.get("author"),
                    "created_at": pr.get("created_at"),
                    "merged_at": pr.get("merged_at"),
                    "title": pr.get("title"),
                    "pr_url": pr.get("url"),
                    "task_id": task_id,
                    "task_url": task_url,
                })
    return results


def add_impact(rows, path):
    """Copy each PR's scores from score_doc_impact.py output onto its rows."""
    scores = {}
    with open(path) as f:
        for line in f:
            if line.strip():
                score = json.loads(line)
                scores[score["pr_number"]] = score
    unscored = {field: "" for field in IMPACT_FIELDS} | {"doc_impact": "unknown"}
    for r in rows:
        score = scores.get(r["pr_number"], unscored)
        r.update({field: score.get(field, "") for field in IMPACT_FIELDS})


def task_impacts(rows):
    """Each task's level: the strongest level among its PRs."""
    impacts = {}
    for r in rows:
        current = impacts.get(r["task_id"], "none")
        impacts[r["task_id"]] = max(current, r["doc_impact"], key=IMPACT_LEVELS.index)
    return impacts


def load_excluded_ids(path, column):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if column not in (reader.fieldnames or []):
            sys.exit(f"Column {column!r} not found in {path}; columns are: {reader.fieldnames}")
        ids = set()
        for row in reader:
            ids.update(task_ids_from_cell(row[column] or ""))
        return ids


def task_ids_from_cell(value):
    """Task IDs in a filter-CSV cell: bare IDs or task URLs, possibly several."""
    value = value.strip()
    if not value:
        return set()
    ids = {m.group(2) for m in TASK_URL_PATTERN.finditer(value)}
    ids |= {m.group(1) for m in PROJECT_TASK_URL_PATTERN.finditer(value)}
    return ids or {value}


def apply_filters(rows, args):
    counts = {"total": len(rows)}

    def drop(label, keep):
        nonlocal rows
        before = len(rows)
        rows = [r for r in rows if keep(r)]
        counts[label] = before - len(rows)

    if args.exclude_author:
        authors = set(args.exclude_author)
        drop("excluded_authors", lambda r: r["author"] not in authors)
    if args.require_task:
        drop("no_task_id", lambda r: r["task_id"])
    if args.exclude_csv:
        excluded = load_excluded_ids(args.exclude_csv, args.exclude_column)
        drop("already_in_csv", lambda r: r["task_id"] not in excluded)
    if args.impact_jsonl:
        add_impact(rows, args.impact_jsonl)
        impacts = task_impacts(rows)
        for level in reversed(IMPACT_LEVELS):
            counts[f"tasks_{level}"] = sum(v == level for v in impacts.values())
        if args.doc_impact == "keep":
            drop("no_doc_impact", lambda r: impacts[r["task_id"]] != "none")
        elif args.doc_impact == "drop":
            drop("had_doc_impact", lambda r: impacts[r["task_id"]] not in HAS_IMPACT)

    counts["kept"] = len(rows)
    task_types = add_task_types(rows)
    counts["unique_tasks"] = len(task_types)
    for kind in reversed(TASK_TYPE_ORDER):
        counts[f"tasks_{kind}"] = sum(v == kind for v in task_types.values())
    return rows, counts


def write_xlsx(rows, path, fields):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "features"
    ws.append(fields)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    link_font = Font(color="0563C1", underline="single")

    for r in rows:
        values = []
        for field in fields:
            value = r.get(field) or ""
            if field in ("task_id", "pr_number") and str(value).isdigit():
                value = int(value)
            values.append(value)
        ws.append(values)
        row_idx = ws.max_row
        for col_idx, field in enumerate(fields, start=1):
            url = r.get(XLSX_LINKS.get(field, ""))
            if url:
                cell = ws.cell(row_idx, col_idx)
                cell.hyperlink = url
                cell.font = link_font

    widths = XLSX_WIDTHS | IMPACT_WIDTHS
    for col_idx, field in enumerate(fields, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = widths[field]
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--exclude-author", action="append", default=[])
    parser.add_argument("--require-task", action="store_true")
    parser.add_argument("--exclude-csv")
    parser.add_argument("--exclude-column", default="RD Task ID")
    parser.add_argument("--xlsx")
    parser.add_argument("--impact-jsonl")
    parser.add_argument("--doc-impact", choices=["keep", "drop", "label"], default="label")
    args = parser.parse_args()
    if args.doc_impact != "label" and not args.impact_jsonl:
        parser.error("--doc-impact keep/drop needs --impact-jsonl")
    if args.impact_jsonl and not args.require_task:
        parser.error("--impact-jsonl needs --require-task (impact is grouped by task)")
    extra = IMPACT_FIELDS if args.impact_jsonl else []

    rows, counts = apply_filters(process(args.inputs), args)

    if args.json:
        json.dump(rows, sys.stdout, indent=2)
        print()
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=CSV_FIELDS + extra)
        writer.writeheader()
        writer.writerows(rows)

    if args.xlsx:
        write_xlsx(rows, args.xlsx, XLSX_FIELDS + extra)

    print(json.dumps(counts), file=sys.stderr)


if __name__ == "__main__":
    main()
