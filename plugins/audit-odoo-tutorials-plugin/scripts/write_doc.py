#!/usr/bin/env python3
"""Write a tutorial audit list to a Google Doc with the gws CLI.

Each app gets its own tab, so one doc can hold the audits of several apps.

Usage:
    python3 write_doc.py list.txt --app MRP                  # create a new doc
    python3 write_doc.py list.txt --app MRP --doc <URL|ID>   # add a tab to a doc

list.txt holds the numbered list from the audit, one video per line:
    1. 2024-08-23 — Vendor Pricelist | Odoo Purchase — https://www.youtube.com/watch?v=...

The tab is named after the app ("MRP"). If the doc already has a tab with that
name, the new tab gets the date too ("MRP (2026-11-11)"). The script never
changes or deletes existing tabs.

Prints the URL of the new tab.
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys

DEFAULT_TITLE = "Odoo Tutorials Audit"
URL_RE = re.compile(r"https?://\S+")


def gws(*args, params=None, body=None):
    cmd = ["gws", *args]
    if params is not None:
        cmd += ["--params", json.dumps(params)]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        sys.exit("gws is not installed. See the README: Set up gws.")
    if res.returncode != 0:
        sys.exit(f"gws failed ({' '.join(args[:3])}): {res.stderr.strip() or res.stdout.strip()}")
    # gws prints "Using keyring backend" on stderr; stdout is pure JSON.
    return json.loads(res.stdout) if res.stdout.strip() else {}


def doc_id_from(value):
    m = re.search(r"/document/d/([A-Za-z0-9_-]+)", value)
    return m.group(1) if m else value.strip()


def u16(text):
    """Length in UTF-16 code units, which is how the Docs API counts indexes."""
    return len(text.encode("utf-16-le")) // 2


def all_tabs(tabs):
    for tab in tabs or []:
        yield tab
        yield from all_tabs(tab.get("childTabs"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("list_file")
    ap.add_argument("--app", required=True, help='app name, e.g. "MRP"')
    ap.add_argument("--doc", help="existing Google Doc URL or ID; omit to create a new doc")
    ap.add_argument("--title", default=DEFAULT_TITLE, help="title of a new doc")
    args = ap.parse_args()

    with open(args.list_file, encoding="utf-8") as f:
        lines = [ln.rstrip() for ln in f if ln.strip()]
    if not lines:
        sys.exit(f"{args.list_file} is empty.")

    today = dt.date.today().isoformat()

    if args.doc:
        doc_id = doc_id_from(args.doc)
        doc = gws("docs", "documents", "get",
                  params={"documentId": doc_id, "includeTabsContent": True})
        taken = {t["tabProperties"].get("title", "") for t in all_tabs(doc.get("tabs"))}
        tab_title = args.app
        if tab_title in taken:
            tab_title = f"{args.app} ({today})"
        if tab_title in taken:
            sys.exit(f'The doc already has a tab named "{tab_title}". Rename it or use another doc.')
        reply = gws("docs", "documents", "batchUpdate", params={"documentId": doc_id},
                    body={"requests": [{"addDocumentTab": {"tabProperties": {"title": tab_title}}}]})
        tab_id = reply["replies"][0]["addDocumentTab"]["tabProperties"]["tabId"]
    else:
        doc = gws("docs", "documents", "create", body={"title": args.title})
        doc_id = doc["documentId"]
        tab_id = doc["tabs"][0]["tabProperties"]["tabId"]
        tab_title = args.app
        gws("docs", "documents", "batchUpdate", params={"documentId": doc_id},
            body={"requests": [{"updateDocumentTabProperties": {
                "tabProperties": {"tabId": tab_id, "title": tab_title}, "fields": "title"}}]})

    heading = f"Odoo {args.app} tutorials (audited {today})"
    # No trailing newline: the tab already ends with an empty paragraph.
    text = heading + "\n" + "\n".join(lines)

    def loc(start, end=None):
        out = {"tabId": tab_id, "startIndex": start}
        if end is not None:
            out["endIndex"] = end
        return out

    requests = [
        {"insertText": {"location": {"tabId": tab_id, "index": 1}, "text": text}},
        {"updateParagraphStyle": {"range": loc(1, 1 + u16(heading)),
                                  "paragraphStyle": {"namedStyleType": "HEADING_2"},
                                  "fields": "namedStyleType"}},
    ]
    # Make each URL a clickable link. Indexes start at 1 (the tab body start).
    pos = 1 + u16(heading) + 1
    for line in lines:
        for m in URL_RE.finditer(line):
            start = pos + u16(line[:m.start()])
            requests.append({"updateTextStyle": {
                "range": loc(start, start + u16(m.group())),
                "textStyle": {"link": {"url": m.group()}}, "fields": "link"}})
        pos += u16(line) + 1

    gws("docs", "documents", "batchUpdate", params={"documentId": doc_id},
        body={"requests": requests})

    print(f'Tab "{tab_title}": https://docs.google.com/document/d/{doc_id}/edit?tab={tab_id}')


if __name__ == "__main__":
    main()
