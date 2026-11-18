#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl"]
# ///
"""
Keep a tracked task list for one repo and branch up to date across runs.

Compares this run's rows (the CSV from extract_task_ids.py, built without
--exclude-csv so covered tasks can be recognized) with the state file from
earlier runs, then rewrites the state file, the spreadsheet and a CSV copy:

  features  Every tracked row. "change" and "changed_on" say what changed in
            this run (new, updated, covered, reactivated, gone). "status" is
            active, covered (in the filter CSV) or gone (no longer on the
            branch). review_status, assignee and notes belong to the writers:
            they are read back from the previous spreadsheet by column name
            and matched by task and PR, so sorting or moving columns is safe.
  Changes   One row per change, newest first.
  Runs      One row per run, newest first.

Usage:
  track_changes.py <rows.csv> --state PATH --xlsx PATH [options]

Options:
  --csv PATH              Also write the tracked list as CSV.
  --filter-csv PATH       Tasks already covered (e.g. release notes). Without it,
                          tasks keep the covered status they already had.
  --filter-column NAME    Its task column (default "RD Task ID").
  --scorer-version V      Version of score_doc_impact.py behind the impact
                          columns. When it differs from the state's, impact
                          columns are refreshed without logging changes.
  --display MODE          label (default) shows every row; keep hides tasks
                          scored "none"; drop hides tasks with an impact.
                          Hidden rows stay tracked in the state file.
  --settings JSON         Run settings to save in the state file.
  --fetched-at TEXT       When the PR list was fetched (shown in Runs).
  --fresh                 Back up the existing state and start over.
  --keep-backups N        Dated backups of the spreadsheet and state to keep
                          (default 12).

If the spreadsheet is open in LibreOffice or Excel, the result is written next
to it as <name>.updated.xlsx and the summary says so; the state is updated
either way, and the next run reads writer columns from the original file.

A one-line JSON summary is printed to stderr.
"""
import argparse
import csv
import glob
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True  # don't leave __pycache__ in the plugin folder
sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_task_ids import (  # noqa: E402
    IMPACT_FIELDS, IMPACT_LEVELS, IMPACT_WIDTHS, XLSX_LINKS, XLSX_WIDTHS, load_excluded_ids,
)

STATE_VERSION = 1
WRITER_FIELDS = ["review_status", "assignee", "notes"]
GENERATED_FIELDS = [
    "task_id", "task_url", "task_type", "pr_number", "pr_url", "tag", "change_type", "title",
    "state", "author", "created_at",
]
TRACK_FIELDS = ["change", "changed_on", "status", "first_seen"]
SHEET_FIELDS = (
    ["change", "changed_on"] + WRITER_FIELDS + ["status"] + GENERATED_FIELDS + ["first_seen"] + IMPACT_FIELDS
)
WIDTHS = XLSX_WIDTHS | IMPACT_WIDTHS | {
    "change": 12, "changed_on": 12, "review_status": 15, "assignee": 14, "notes": 40,
    "status": 10, "first_seen": 12,
}
# Fields whose change is worth telling a writer about. Titles, authors and
# module lists change for cosmetic reasons and are just refreshed.
WATCHED = ["state", "tag", "change_type", "task_type", "doc_impact", "matched_labels"]
IMPACT_WATCHED = {"doc_impact", "matched_labels"}
HAS_IMPACT = {"possible", "likely", "confirmed"}
STATUS_ORDER = {"active": 0, "covered": 1, "gone": 2}

FILLS = {  # change value -> cell color
    "new": "E2F3EA", "updated": "FFF4CC", "covered": "ECEBF1", "gone": "F8E4E4", "reactivated": "E3EDF8",
}
CHANGED_CELL = "FFF4CC"
WRITER_HEADER = "EFE8F7"


def key_of(task_id, pr_number):
    return f"{int(task_id)}:{int(pr_number)}"


def load_state(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"version": STATE_VERSION, "rows": {}, "changes": [], "runs": []}


def read_writer_values(xlsx_path):
    """Writer columns from the previous spreadsheet, by task and PR."""
    if not os.path.exists(xlsx_path):
        return {}
    from openpyxl import load_workbook
    try:
        wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    except Exception as e:  # a corrupt or half-saved file must not block the run
        print(f"Couldn't read writer columns from {xlsx_path}: {e}", file=sys.stderr)
        return {}
    if "features" not in wb.sheetnames:
        return {}
    rows = wb["features"].iter_rows(values_only=True)
    header = [str(h or "").strip() for h in next(rows, [])]
    col = {name: i for i, name in enumerate(header)}
    if "task_id" not in col or "pr_number" not in col:
        return {}
    values = {}
    for row in rows:
        task, pr = row[col["task_id"]], row[col["pr_number"]]
        if task in (None, "") or pr in (None, ""):
            continue
        try:
            key = key_of(task, pr)
        except (TypeError, ValueError):
            continue
        values[key] = {f: ("" if row[col[f]] is None else str(row[col[f]])) for f in WRITER_FIELDS if f in col}
    wb.close()
    return values


def is_locked(path):
    p = Path(path)
    return (p.parent / f".~lock.{p.name}#").exists() or (p.parent / f"~${p.name}").exists()


def backup(path, history_dir, stamp, keep):
    """Copy path into history_dir with a timestamp, then prune old copies."""
    if not os.path.exists(path):
        return
    os.makedirs(history_dir, exist_ok=True)
    p = Path(path)
    shutil.copy2(path, Path(history_dir) / f"{p.stem}_{stamp}{p.suffix}")
    copies = sorted(glob.glob(str(Path(history_dir) / f"{p.stem}_*{p.suffix}")))
    for old in copies[:-keep] if keep > 0 else []:
        os.remove(old)


def task_levels(rows):
    levels = {}
    for r in rows:
        if r.get("doc_impact"):
            levels[r["task_id"]] = max(levels.get(r["task_id"], "none"), r["doc_impact"], key=IMPACT_LEVELS.index)
    return levels


def update(state, fresh_rows, has_impact, covered, scorer_version, writer_values, today):
    """Apply this run to the state. Returns (summary counts, highlights)."""
    rows = state["rows"]
    first_run = not rows
    scorer_changed = bool(has_impact and not first_run and scorer_version
                          and state.get("scorer_version") not in (None, scorer_version))
    changes = []
    seen = set()

    def log(r, field, old, new):
        changes.append({"date": today, "task_id": r["task_id"], "pr_number": r["pr_number"],
                        "title": r.get("title", ""), "field": field, "old": old, "new": new})

    for fresh in fresh_rows:
        key = key_of(fresh["task_id"], fresh["pr_number"])
        seen.add(key)
        rec = rows.get(key)
        values = {f: fresh.get(f, "") or "" for f in GENERATED_FIELDS}
        if has_impact:
            values |= {f: fresh.get(f, "") or "" for f in IMPACT_FIELDS}
        if covered is None:  # no filter CSV this run: keep what earlier runs found
            status = "covered" if rec and rec.get("status") == "covered" else "active"
        else:
            status = "covered" if fresh["task_id"] in covered else "active"

        if rec is None:
            rec = {"first_seen": today, **{f: "" for f in WRITER_FIELDS + IMPACT_FIELDS}}
            change, changed_fields = "new", []
            if not first_run:
                log(values, "row", "", "added")
        else:
            changed_fields = []
            for f in WATCHED:
                if f in IMPACT_WATCHED and (not has_impact or scorer_changed):
                    continue
                old, new = rec.get(f, ""), values.get(f, rec.get(f, ""))
                if old != new:
                    changed_fields.append(f)
                    log(values, f, old, new)
            old_status = rec.get("status", "active")
            if old_status != status:
                log(values, "status", old_status, status)
                change = "covered" if status == "covered" else "reactivated"
            else:
                change = "updated" if changed_fields else ""

        rec |= values
        rec.update(status=status, last_seen=today, change=change, changed_fields=changed_fields)
        if change:
            rec["changed_on"] = today
        rec.setdefault("changed_on", today)
        rec |= writer_values.get(key, {})
        rows[key] = rec

    for key, rec in rows.items():
        if key in seen:
            continue
        if rec.get("status") != "gone":
            log(rec, "status", rec.get("status", "active"), "gone")
            rec.update(status="gone", change="gone", changed_on=today, changed_fields=[])
        else:
            rec.update(change="", changed_fields=[])
        rec |= writer_values.get(key, {})

    if first_run:
        changes.append({"date": today, "task_id": "", "pr_number": "", "title": "", "field": "tracking",
                        "old": "", "new": f"started with {len(rows)} rows"})
    if scorer_changed:
        changes.append({"date": today, "task_id": "", "pr_number": "", "title": "", "field": "scorer_version",
                        "old": state.get("scorer_version"), "new": scorer_version})
    if has_impact and scorer_version:
        state["scorer_version"] = scorer_version
    state["changes"] = changes + state.get("changes", [])

    # Summary, per task where it matters to writers.
    all_rows = list(rows.values())
    by_change = {}
    for r in all_rows:
        by_change.setdefault(r["change"], set()).add(r["task_id"])
    known_before = {r["task_id"] for r in all_rows if r["change"] != "new"}
    new_tasks = by_change.get("new", set()) - known_before
    summary = {
        "first_run": first_run,
        "rows": len(all_rows),
        "tasks_active": len({r["task_id"] for r in all_rows if r["status"] == "active"}),
        "new_tasks": len(new_tasks),
        "new_prs_on_known_tasks": sum(1 for r in all_rows if r["change"] == "new" and r["task_id"] in known_before),
        "updated_tasks": len(by_change.get("updated", set())),
        "covered_tasks": len(by_change.get("covered", set())),
        "reactivated_tasks": len(by_change.get("reactivated", set())),
        "gone_rows": sum(1 for r in all_rows if r["change"] == "gone"),
        "scorer_refreshed": scorer_changed,
    }
    if has_impact:
        levels = task_levels([r for r in all_rows if r["task_id"] in new_tasks])
        summary["new_tasks_likely_or_confirmed"] = sum(v in ("likely", "confirmed") for v in levels.values())

    highlights = []
    if not first_run:
        for c in changes:
            if c["field"] == "doc_impact" and c["new"] in ("confirmed", "likely"):
                highlights.append(f"task {c['task_id']} (PR {c['pr_number']}): impact {c['old']} -> {c['new']}")
            elif c["field"] == "task_type":
                highlights.append(f"task {c['task_id']}: type {c['old']} -> {c['new']}")
    return summary, highlights[:10]


def display_rows(rows, mode):
    rows = list(rows)
    if mode in ("keep", "drop"):
        levels = task_levels(rows)
        if mode == "keep":
            rows = [r for r in rows if levels.get(r["task_id"], "unknown") != "none"]
        else:
            rows = [r for r in rows if levels.get(r["task_id"], "unknown") not in HAS_IMPACT]
    return sorted(rows, key=lambda r: (r.get("change", "") == "", STATUS_ORDER.get(r.get("status"), 9),
                                       -int(r["task_id"]), int(r["pr_number"])))


def write_xlsx(path, rows, state):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    def fill(color):
        return PatternFill("solid", start_color=color, end_color=color)

    wb = Workbook()
    ws = wb.active
    ws.title = "features"
    ws.append(SHEET_FIELDS)
    for i, cell in enumerate(ws[1]):
        cell.font = Font(bold=True)
        if SHEET_FIELDS[i] in WRITER_FIELDS:
            cell.fill = fill(WRITER_HEADER)
    link_font = Font(color="0563C1", underline="single")
    for r in rows:
        ws.append([int(r[f]) if f in ("task_id", "pr_number") and str(r.get(f, "")).isdigit() else (r.get(f) or "")
                   for f in SHEET_FIELDS])
        row_idx = ws.max_row
        for col_idx, field in enumerate(SHEET_FIELDS, start=1):
            cell = ws.cell(row_idx, col_idx)
            url = r.get(XLSX_LINKS.get(field, ""))
            if url:
                cell.hyperlink = url
                cell.font = link_font
            if field == "change" and r.get("change") in FILLS:
                cell.fill = fill(FILLS[r["change"]])
            elif field in r.get("changed_fields", []):
                cell.fill = fill(CHANGED_CELL)
    for col_idx, field in enumerate(SHEET_FIELDS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = WIDTHS.get(field, 14)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    for title, fields, items in (
        ("Changes", ["date", "task_id", "pr_number", "title", "field", "old", "new"], state["changes"]),
        ("Runs", ["date", "fetched_at", "rows", "tasks_active", "new_tasks", "new_prs_on_known_tasks",
                  "updated_tasks", "covered_tasks", "reactivated_tasks", "gone_rows", "note"], state["runs"]),
    ):
        sheet = wb.create_sheet(title)
        sheet.append(fields)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for item in items:
            sheet.append([item.get(f, "") if item.get(f) is not None else "" for f in fields])
        for col_idx, field in enumerate(fields, start=1):
            sheet.column_dimensions[get_column_letter(col_idx)].width = 60 if field == "title" else 16
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions

    tmp = Path(path).with_name(f".{Path(path).name}.tmp")
    wb.save(tmp)
    os.replace(tmp, path)


def write_csv(path, rows):
    tmp = f"{path}.tmp"
    with open(tmp, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SHEET_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("rows_csv")
    parser.add_argument("--state", required=True)
    parser.add_argument("--xlsx", required=True)
    parser.add_argument("--csv")
    parser.add_argument("--filter-csv")
    parser.add_argument("--filter-column", default="RD Task ID")
    parser.add_argument("--scorer-version")
    parser.add_argument("--display", choices=["label", "keep", "drop"], default="label")
    parser.add_argument("--settings")
    parser.add_argument("--fetched-at", default="")
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--keep-backups", type=int, default=12)
    args = parser.parse_args()

    now = datetime.now()
    today, stamp = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d_%H%M%S")
    history = str(Path(args.xlsx).parent / "history")  # spreadsheet backups, next to the spreadsheet
    state_history = str(Path(args.state).parent / "history")  # state backups, next to the state

    with open(args.rows_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        has_impact = "doc_impact" in (reader.fieldnames or [])
        fresh_rows = [r for r in reader if (r.get("task_id") or "").strip() and (r.get("pr_number") or "").strip()]

    if args.fresh:
        backup(args.state, state_history, stamp, args.keep_backups)
        backup(args.xlsx, history, stamp, args.keep_backups)
        state = load_state("/nonexistent")
        writer_values = {}
    else:
        state = load_state(args.state)
        if state.get("version", STATE_VERSION) > STATE_VERSION:
            sys.exit(f"{args.state} was written by a newer version of this script")
        writer_values = read_writer_values(args.xlsx)

    covered = load_excluded_ids(args.filter_csv, args.filter_column) if args.filter_csv else None
    summary, highlights = update(state, fresh_rows, has_impact, covered, args.scorer_version, writer_values, today)
    if args.settings:
        state["settings"] = json.loads(args.settings)

    rows = display_rows(state["rows"].values(), args.display)
    target, note = args.xlsx, ""
    if is_locked(args.xlsx):
        target = str(Path(args.xlsx).with_name(f"{Path(args.xlsx).stem}.updated.xlsx"))
        note = f"spreadsheet was open; result saved as {Path(target).name}"
    elif not args.fresh:
        backup(args.xlsx, history, stamp, args.keep_backups)

    run = {"date": now.strftime("%Y-%m-%d %H:%M"), "fetched_at": args.fetched_at,
           **{k: summary[k] for k in ("rows", "tasks_active", "new_tasks", "new_prs_on_known_tasks",
                                      "updated_tasks", "covered_tasks", "reactivated_tasks", "gone_rows")},
           "note": "; ".join(n for n in (note, "scorer updated: impact refreshed without logging"
                                          if summary["scorer_refreshed"] else "") if n)}
    state["runs"] = [run] + state.get("runs", [])
    state["version"] = STATE_VERSION

    write_xlsx(target, rows, state)
    if target == args.xlsx:
        stale = Path(args.xlsx).with_name(f"{Path(args.xlsx).stem}.updated.xlsx")
        if stale.exists():
            stale.unlink()
    if args.csv:
        write_csv(args.csv, rows)

    if not args.fresh:
        backup(args.state, state_history, stamp, args.keep_backups)
    tmp = f"{args.state}.tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, args.state)

    previous = state["runs"][1]["date"] if len(state["runs"]) > 1 else None
    print(json.dumps({**summary, "previous_run": previous, "shown_rows": len(rows), "xlsx": target,
                      "note": run["note"], "highlights": highlights}), file=sys.stderr)


if __name__ == "__main__":
    main()
