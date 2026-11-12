#!/usr/bin/env python3
"""Build a tutorial-audit Google Sheet with the gws CLI.

Usage:
    python3 build_sheet.py audit.json            # create the Google Sheet
    python3 build_sheet.py audit.json --dry-run  # print rows only

Input JSON:
{
  "title": "Purchase Video Audit (2026-10-22)",
  "app": "Purchase",
  "videos": [
    {"date": "2024-08-23", "topic": "Vendor Pricelist | Odoo Purchase",
     "url": "https://www.youtube.com/watch?v=...",
     "dup_group": null}     # same string = same topic re-recorded
  ]
}
"""
import datetime as dt
import json
import subprocess
import sys

# Publish-date cutoffs (team rules). Edit here if they change.
# (first day of range, version, category). Category 1 = needs archive or redo.
RANGES = [
    (dt.date.min,          "V16",          1),
    (dt.date(2023, 11, 8), "V17",          1),
    (dt.date(2024, 10, 4), "V18",          2),
    (dt.date(2025, 9, 19), "V19",          3),
    (dt.date(2026, 9, 26), "V20",          3),
]
VERSIONS = [r[1] for r in RANGES]

# Google Sheet whose row 2 holds the Version / Duplicates / Priority dropdowns
# with their chip colors. The Sheets API can't set chip colors, but copying a
# dropdown keeps them, so every new sheet is a copy of this template and the
# row 2 dropdowns are pasted down. To change a color or add a version (e.g.
# V21), edit the dropdowns in the template in the Sheets UI.
TEMPLATE_ID = "1xVLRkJ8qET9bOo2ziRmER3UV3NkMF7Ty-aE8s1V9quc"
UPDATE_TAB_ID = 2  # fixed sheetId for the Tutorials to Update tab

HEADER = ["Creation Date", "Topic", "Link", "Version", "Duplicates", "Priority", "Reason"]
WIDTHS = [104, 405, 229, 77, 83, 85, 419]
UPDATE_HEADER = ["Existing tutorials", "Potential videos to write or refresh", "", "Task link"]
UPDATE_WIDTHS = [499, 288, 100, 100]
GREY = {"red": 0.6, "green": 0.6, "blue": 0.6}
BLUE = {"red": 0, "green": 0, "blue": 1}
DARK_RED = {"red": 0.596, "green": 0, "blue": 0}  # #980000, as in the team sheet
GREEN = {"red": 0.416, "green": 0.659, "blue": 0.310}  # #6AA84F, as in the team sheet


def classify(day):
    match = RANGES[0]
    for r in RANGES:
        if day >= r[0]:
            match = r
    return match[1], match[2]


def build(data):
    """Return (rows, meta, update_rows).

    rows/meta: the Video List tab (meta[i] has the archived flag for data row i).
    update_rows: the Tutorials to Update tab.
    """
    videos = sorted(data["videos"], key=lambda v: v["date"])
    for v in videos:
        v["_day"] = dt.date.fromisoformat(v["date"])
        v["_version"], v["_cat"] = classify(v["_day"])

    groups = {}
    for v in videos:
        if v.get("dup_group"):
            groups.setdefault(v["dup_group"], []).append(v)

    # Sheet line of each video: row 1 is the header, and rows follow date order.
    line = {id(v): i + 2 for i, v in enumerate(videos)}

    rows, meta = [HEADER], []
    for v in videos:
        others = [o for o in groups.get(v.get("dup_group"), []) if o is not v]
        own = VERSIONS.index(v["_version"])
        # Only list older versions: newer ones (shown in Reason) and the video's own version are noise.
        dups = ", ".join(sorted({o["_version"] for o in others
                                 if VERSIONS.index(o["_version"]) < own}, key=VERSIONS.index))
        later = [o for o in others if o["_day"] > v["_day"]]
        newer = [o for o in later if o["_cat"] != 1]
        archived = v["_cat"] == 1 and bool(newer)
        if v["_cat"] == 1 and not newer:
            priority = "High"
        elif v["_version"] == "V18" and not later:
            priority = "Low"
        else:
            priority = ""
        parts, link = [], None
        if priority == "High":
            parts.append("No newer videos")
        if archived:
            link = newer[-1]["url"]  # the newest re-recording
            parts.append(f"Archive. Redirect to {link}")
        if later:
            nums = [str(line[id(o)]) for o in later]
            parts.append(f"Redone on line{'s' if len(nums) > 1 else ''} {', '.join(nums)}")
        rows.append([v["date"], v["topic"], v["url"], v["_version"],
                     dups, priority, "\n".join(parts)])
        meta.append({"archived": archived, "link": link})

    # Tutorials to Update. Column A: one entry per topic (the newest video of a
    # duplicate group). Column B: starts with the High-priority videos.
    # Columns C (writer) and D (task link) are left for a person to fill in.
    unique = [v for v in videos
              if not v.get("dup_group") or v is groups[v["dup_group"]][-1]]
    high = [r[1] for r in rows[1:] if r[5] == "High"]
    newest = int(VERSIONS[-1].lstrip("V"))
    app = data.get("app") or videos[0]["topic"].rsplit("| Odoo ", 1)[-1].strip()
    update_rows = [[f"Odoo {newest} {app} Tutorials"],
                   UPDATE_HEADER]
    for i in range(max(len(unique), len(high))):
        update_rows.append([unique[i]["topic"] if i < len(unique) else "",
                            high[i] if i < len(high) else "", "", ""])
    return rows, meta, update_rows


def gws(*args, body=None):
    cmd = ["gws", *args]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"gws failed ({' '.join(args[:3])}): {res.stderr.strip() or res.stdout.strip()}")
    # gws prints "Using keyring backend" on stderr; stdout is pure JSON.
    return json.loads(res.stdout) if res.stdout.strip() else {}


def rng(sheet_id, r0, r1, c0=None, c1=None):
    out = {"sheetId": sheet_id, "startRowIndex": r0, "endRowIndex": r1}
    if c0 is not None:
        out.update(startColumnIndex=c0, endColumnIndex=c1)
    return out


def fmt(range_, user_fmt, fields):
    return {"repeatCell": {"range": range_, "cell": {"userEnteredFormat": user_fmt}, "fields": fields}}




def key_cell(sheet_id, row):
    """Color key, two blank rows under the list, with "Red"/"Green" colored."""
    v = f"v{VERSIONS[-1].lstrip('V')}"
    text = f"Key:\nRed: Replaced in {v}\nGreen: New in {v}"
    red_at, green_at = text.index("Red"), text.index("Green")
    runs = [{"startIndex": 0, "format": {}},
            {"startIndex": red_at, "format": {"foregroundColor": DARK_RED}},
            {"startIndex": red_at + 3, "format": {}},
            {"startIndex": green_at, "format": {"foregroundColor": GREEN}},
            {"startIndex": green_at + 5, "format": {}}]
    return {"updateCells": {
        "start": {"sheetId": sheet_id, "rowIndex": row, "columnIndex": 0},
        "rows": [{"values": [{"userEnteredValue": {"stringValue": text}, "textFormatRuns": runs}]}],
        "fields": "userEnteredValue,textFormatRuns"}}


def warn_missing_dropdown_values(doc_id, rows):
    """Warn (stderr) when the data uses values the template dropdowns don't list.

    The dropdowns are strict, so such cells show as invalid. The fix is to add
    the value to the template's row 2 dropdown in the Sheets UI (never via API).
    """
    got = gws("sheets", "spreadsheets", "get", "--params", json.dumps({
        "spreadsheetId": doc_id, "ranges": "Video List!D2:F2", "includeGridData": True,
        "fields": "sheets.data.rowData.values.dataValidation.condition.values"}))
    cells = got["sheets"][0]["data"][0]["rowData"][0]["values"]
    allowed = [{v["userEnteredValue"].strip() for v in c.get("dataValidation", {})
                .get("condition", {}).get("values", [])} for c in cells]
    for col, name in ((0, "Version"), (1, "Duplicates")):
        used = {x.strip() for r in rows[1:] for x in r[3 + col].split(",") if x.strip()}
        missing = sorted(used - allowed[col], key=lambda x: VERSIONS.index(x) if x in VERSIONS else 99)
        if missing:
            print(f"WARNING: template {name} dropdown is missing {', '.join(missing)}. "
                  f"Add it in the template (Data > Data validation on row 2).", file=sys.stderr)
    if any("," in r[4] for r in rows[1:]):
        print("NOTE: some Duplicates cells hold several versions. They're only valid if the "
              "template's Duplicates dropdown has 'Allow multiple selections' turned on.",
              file=sys.stderr)


def create_sheet(title, rows, meta, update_rows):
    doc_id = gws("drive", "files", "copy", "--params", json.dumps({"fileId": TEMPLATE_ID}),
                 body={"name": title})["id"]
    info = gws("sheets", "spreadsheets", "get",
               "--params", json.dumps({"spreadsheetId": doc_id, "fields": "sheets.properties"}))
    sid = next(x["properties"]["sheetId"] for x in info["sheets"]
               if x["properties"]["title"] == "Video List")
    uid = UPDATE_TAB_ID
    # The template has an unused column D (old Tags column). Delete it in the copy so
    # its colored dropdowns move from E:G to D:F, under Version, Duplicates and Priority.
    gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": doc_id}),
        body={"requests": [{"deleteDimension": {"range": {
            "sheetId": sid, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 4}}}]})
    warn_missing_dropdown_values(doc_id, rows)
    gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": doc_id}),
        body={"requests": [{"addSheet": {"properties": {"sheetId": uid, "title": "Tutorials to Update"}}}]})

    # USER_ENTERED turns ISO dates into real dates.
    gws("sheets", "spreadsheets", "values", "update",
        "--params", json.dumps({"spreadsheetId": doc_id, "range": "Video List!A1",
                                "valueInputOption": "USER_ENTERED"}),
        body={"values": rows})
    gws("sheets", "spreadsheets", "values", "update",
        "--params", json.dumps({"spreadsheetId": doc_id, "range": "Tutorials to Update!A1",
                                "valueInputOption": "RAW"}),
        body={"values": update_rows})

    n, ncol = len(rows), len(HEADER)
    wrap_top = {"textFormat": {"fontSize": 11}, "verticalAlignment": "TOP", "wrapStrategy": "WRAP"}

    reqs = [
        fmt(rng(sid, 0, 1, 0, ncol), {"textFormat": {"bold": True}, "horizontalAlignment": "CENTER"},
            "userEnteredFormat(textFormat.bold,horizontalAlignment)"),
        {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                                   "fields": "gridProperties.frozenRowCount"}},
        {"setBasicFilter": {"filter": {"range": rng(sid, 0, n, 0, ncol)}}},
        fmt(rng(sid, 1, n, 0, 1), {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"},
                                   "textFormat": {"fontSize": 11, "foregroundColor": GREY}},
            "userEnteredFormat(numberFormat,textFormat)"),
        fmt(rng(sid, 1, n, 1, 2), wrap_top, "userEnteredFormat(textFormat,verticalAlignment,wrapStrategy)"),
        fmt(rng(sid, 1, n, 6, 7), wrap_top, "userEnteredFormat(textFormat,verticalAlignment,wrapStrategy)"),
        fmt(rng(sid, 0, n, 2, 3), {"wrapStrategy": "CLIP"}, "userEnteredFormat.wrapStrategy"),
        # Paste the template's colored dropdowns (row 2, D:F) onto every data row.
        {"copyPaste": {"source": rng(sid, 1, 2, 3, 6), "destination": rng(sid, 1, n, 3, 6),
                       "pasteType": "PASTE_DATA_VALIDATION"}},
    ]
    for i, w in enumerate(WIDTHS):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"}})

    border = {"style": "SOLID", "width": 1, "color": {}}
    for r, (row, m) in enumerate(zip(rows[1:], meta), start=1):
        reqs.append(fmt(rng(sid, r, r + 1, 2, 3),
                        {"textFormat": {"fontSize": 12, "foregroundColor": BLUE, "link": {"uri": row[2]},
                                        "strikethrough": m["archived"]}},
                        "userEnteredFormat.textFormat"))
        if m["archived"]:
            # Strike through every column except Link (handled above) and Reason.
            for c0, c1 in ((0, 2), (3, 6)):
                reqs.append(fmt(rng(sid, r, r + 1, c0, c1), {"textFormat": {"strikethrough": True}},
                                "userEnteredFormat.textFormat.strikethrough"))
        if m["link"]:
            # Make the redirect URL in Reason clickable.
            start = row[6].index(m["link"])
            runs = [{"startIndex": 0, "format": {}},
                    {"startIndex": start, "format": {"link": {"uri": m["link"]}}}]
            if start + len(m["link"]) < len(row[6]):
                runs.append({"startIndex": start + len(m["link"]), "format": {}})
            reqs.append({"updateCells": {
                "start": {"sheetId": sid, "rowIndex": r, "columnIndex": 6},
                "rows": [{"values": [{"textFormatRuns": runs}]}], "fields": "textFormatRuns"}})
        if row[5] == "High":
            reqs.append(fmt(rng(sid, r, r + 1, 5, 6),
                            {"borders": {k: border for k in ("top", "bottom", "left", "right")}},
                            "userEnteredFormat.borders"))

    # Tutorials to Update formatting (same as the team's sheet).
    un = len(update_rows)
    reqs += [key_cell(uid, un + 2), 
        fmt(rng(uid, 0, 1, 0, 1), {"textFormat": {"bold": True, "fontSize": 14}},
            "userEnteredFormat.textFormat"),
        fmt(rng(uid, 1, 2, 0, 4), {"textFormat": {"bold": True}}, "userEnteredFormat.textFormat.bold"),
        fmt(rng(uid, 2, un, 0, 2), wrap_top, "userEnteredFormat(textFormat,verticalAlignment,wrapStrategy)"),
        fmt(rng(uid, 2, un, 3, 4), {"wrapStrategy": "CLIP"}, "userEnteredFormat.wrapStrategy"),
        # Column A title turns dark red when it's also listed in column B. A rule
        # (not a fixed color) so titles added to B later are picked up too.
        # "=" comparison instead of COUNTIF: no wildcard surprises with "?" or "*".
        {"addConditionalFormatRule": {"index": 0, "rule": {
            "ranges": [{"sheetId": uid, "startRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 1}],
            "booleanRule": {
                "condition": {"type": "CUSTOM_FORMULA", "values": [
                    {"userEnteredValue": '=AND($A3<>"", SUMPRODUCT(--($B$3:$B=$A3))>0)'}]},
                "format": {"textFormat": {"foregroundColor": DARK_RED}}}}}},
    ]
    for i, w in enumerate(UPDATE_WIDTHS):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": uid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"}})

    gws("sheets", "spreadsheets", "batchUpdate",
        "--params", json.dumps({"spreadsheetId": doc_id}), body={"requests": reqs})
    return f"https://docs.google.com/spreadsheets/d/{doc_id}/edit"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    rows, meta, update_rows = build(data)
    if "--dry-run" in sys.argv:
        print("=== Video List")
        for row, m in zip(rows, [{}] + meta):
            print(("~~ " if m.get("archived") else "") + " | ".join(str(c) for c in row))
        print("=== Tutorials to Update")
        for row in update_rows:
            print(" | ".join(str(c) for c in row).rstrip(" |"))
        key = key_cell(0, len(update_rows) + 2)["updateCells"]["rows"][0]["values"][0]
        print(f"\n\n[row {len(update_rows) + 3}] " + key["userEnteredValue"]["stringValue"].replace("\n", " / "))
        return
    print(create_sheet(data["title"], rows, meta, update_rows))


if __name__ == "__main__":
    main()
