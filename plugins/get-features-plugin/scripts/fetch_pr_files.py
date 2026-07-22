#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
Fetch the changed files, with their diffs, of every PR listed in a task CSV
(the output of extract_task_ids.py), and write one JSON object per PR to
stdout:

  {"pr_number": 123, "title": "...", "files": [{"path": "...", "change": "modified", "patch": "@@ ..."}]}

"files" is null when the PR couldn't be fetched or its diff can't be trusted,
and "note" then says why. "patch" is null for binary files and for diffs
GitHub considers too large to show.

A PR opened from the wrong branch (e.g. master into a stable branch, then
closed) can list thousands of commits; GitHub then returns a truncated,
unrelated file list. PRs with 100+ files are checked against the PR's own
changed_files count and skipped when it doesn't match.

Usage:
  fetch_pr_files.py <OWNER/REPO> <task_ids.csv> > pr_files.jsonl
  fetch_pr_files.py <OWNER/REPO> <task_ids.csv> --output pr_files.jsonl

Options:
  --workers N   Requests run in parallel (default 6).
  --output PATH Write to PATH instead of stdout. If PATH already exists, it
                is used as a cache: closed PRs found there with a usable diff
                aren't fetched again (Odoo merges PRs by closing them, and a
                closed PR's diff no longer changes). PATH is replaced only
                once the run succeeds.

A one-line JSON summary is printed to stderr: prs, fetched, cached, missing,
seconds.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

RETRIES = 3
SUSPICIOUS_FILE_COUNT = 100


def read_prs(path):
    """Return {pr_number: (title, state)} for the CSV's unique PRs."""
    prs = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            number = (row.get("pr_number") or "").strip()
            if number.isdigit():
                prs.setdefault(int(number), (row.get("title") or "", row.get("state") or ""))
    return prs


def read_cache(path):
    """Return {pr_number: record} for PRs with a usable diff in an earlier output."""
    cache = {}
    if path and os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    if record.get("files") is not None:
                        cache[record["pr_number"]] = record
    return cache


def gh_json(*args):
    proc = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
    return json.loads(proc.stdout) if proc.returncode == 0 else None


def check_large(repo, number, files):
    """Return a note if a large file list doesn't match the PR's own counts."""
    pr = gh_json(f"repos/{repo}/pulls/{number}")
    if pr is None:
        return "couldn't verify a large diff"
    if pr.get("changed_files") != len(files):
        return f"diff can't be trusted ({pr.get('commits')} commits, {pr.get('changed_files')} files reported)"
    return None


def fetch_files(repo, number):
    """Return (files, note): the PR's changed files, or None and why."""
    for attempt in range(RETRIES):
        proc = subprocess.run(
            ["gh", "api", f"repos/{repo}/pulls/{number}/files?per_page=100", "--paginate",
             "--jq", ".[] | {path: .filename, change: .status, patch}"],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            files = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
            note = check_large(repo, number, files) if len(files) >= SUSPICIOUS_FILE_COUNT else None
            return (None, note) if note else (files, None)
        if "HTTP 401" in proc.stderr:
            sys.exit(f"GitHub authentication failed: {proc.stderr.strip()}")
        if "HTTP 404" in proc.stderr:
            return None, "PR not found"
        time.sleep(2 ** attempt)  # 502/504 and secondary rate limits are usually transient
    print(f"Giving up on PR #{number}", file=sys.stderr)
    return None, "fetch failed"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo", help="OWNER/REPO, e.g. odoo/odoo")
    parser.add_argument("csv", help="task CSV with pr_number (and optionally title, state) columns")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--output", help="write here instead of stdout, reusing it as a cache")
    args = parser.parse_args()

    if args.repo.count("/") != 1:
        sys.exit(f"Expected OWNER/REPO, got {args.repo!r}")

    start = time.monotonic()
    prs = read_prs(args.csv)
    cache = read_cache(args.output)
    reuse = {n for n, (_, state) in prs.items() if state == "closed" and n in cache}
    to_fetch = [n for n in prs if n not in reuse]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        fetched = dict(zip(to_fetch, pool.map(lambda n: fetch_files(args.repo, n), to_fetch)))

    lines = []
    for number, (title, _) in prs.items():
        if number in reuse:
            record = cache[number] | {"title": title}
        else:
            pr_files, note = fetched[number]
            record = {"pr_number": number, "title": title, "files": pr_files}
            if note:
                record["note"] = note
        lines.append(json.dumps(record) + "\n")

    if args.output:
        tmp = f"{args.output}.tmp"
        with open(tmp, "w") as f:
            f.writelines(lines)
        os.replace(tmp, args.output)
    else:
        sys.stdout.writelines(lines)

    ok = sum(files is not None for files, _ in fetched.values())
    print(json.dumps({
        "prs": len(prs),
        "fetched": ok,
        "cached": len(reuse),
        "missing": len(to_fetch) - ok,
        "seconds": round(time.monotonic() - start, 1),
    }), file=sys.stderr)


if __name__ == "__main__":
    main()
