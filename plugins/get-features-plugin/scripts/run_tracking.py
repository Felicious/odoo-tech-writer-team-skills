#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
Run the whole get-features pipeline for one repo and branch and update its
tracked task list. Needs no questions, so it can run from cron.

Each tracked list lives in its own folder, <OUT>/<BRANCH>_<REPO_SLUG>/:

  tasks.xlsx      the spreadsheet
  tasks.csv       the same list as CSV
  history/        dated backups of the spreadsheet
  .data/          state file, PR list, diffs, scores and their backups

OUT is --out, else $GET_FEATURES_HOME, else ~/Documents/get-features.

First run (settings are saved in the state file):
  run_tracking.py --repo odoo/odoo --branch saas-19.3 \\
      [--filter-csv PATH [--filter-column NAME]] [--docs-repo PATH] \\
      [--impact label|keep|drop|skip] [--include-fw-bot] [--out DIR]

Later runs reuse the saved settings; any option given overrides the saved
one and is saved:
  run_tracking.py --repo odoo/odoo --branch saas-19.3

The filter CSV is the exception: it's never saved, and is used only on runs
where --filter-csv is passed. Runs without it keep the covered marks that
earlier runs set.

Other options:
  --skip-fetch   Reuse the PR list fetched last time.
  --fresh        Back up the tracked list and start over.

Steps: fetch the branch's PRs, extract tasks, fetch diffs (closed PRs are
cached), score documentation impact, then track_changes.py. Progress goes
to stderr; the last line on stdout is track_changes.py's JSON summary plus
the output paths.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Saved with the list and reused by later runs. The filter CSV isn't: it's used
# only on the runs where it's passed, and other runs keep earlier covered marks.
SETTING_KEYS = ["repo", "branch", "docs_repo", "impact", "include_fw_bot"]
PATH_KEYS = {"docs_repo"}
DEFAULT_OUT = "~/Documents/get-features"


def list_dir(out, repo, branch):
    """The folder of one tracked list."""
    root = out or os.environ.get("GET_FEATURES_HOME") or DEFAULT_OUT
    return Path(root).expanduser().resolve() / f"{branch}_{repo.replace('/', '_')}"


def say(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", file=sys.stderr, flush=True)


def run(cmd, stdout=None):
    """Run a step; return its stderr's last line (the scripts' JSON summaries)."""
    proc = subprocess.run(cmd, stdout=stdout, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        sys.exit(f"Step failed: {' '.join(map(str, cmd))}\n{proc.stderr.strip()}")
    lines = [line for line in proc.stderr.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def script(name):
    return ["uv", "run", "--quiet", str(HERE / name)]


def docs_ref(repo, branch):
    for ref in (f"origin/{branch}", "origin/master"):
        if subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "-q", ref],
                          capture_output=True).returncode == 0:
            return ref
    return "HEAD"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--out", help="parent folder of tracked lists (default: $GET_FEATURES_HOME "
                                      f"or {DEFAULT_OUT})")
    parser.add_argument("--filter-csv")
    parser.add_argument("--filter-column")
    parser.add_argument("--docs-repo")
    parser.add_argument("--impact", choices=["label", "keep", "drop", "skip"])
    parser.add_argument("--include-fw-bot", action="store_true", default=None)
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()

    folder = list_dir(args.out, args.repo, args.branch)
    data = folder / ".data"
    data.mkdir(parents=True, exist_ok=True)
    paths = {
        "prs": data / "prs.jsonl", "rows": data / "rows.csv", "files": data / "pr_files.jsonl",
        "impact": data / "pr_impact.jsonl", "state": data / "state.json",
        "csv": folder / "tasks.csv", "xlsx": folder / "tasks.xlsx",
    }

    # Settings: saved ones first, then anything given on the command line.
    settings = {}
    if paths["state"].exists():
        with open(paths["state"]) as f:
            settings = json.load(f).get("settings", {})
    for key in SETTING_KEYS:
        value = getattr(args, key)
        if value is not None:
            settings[key] = str(Path(value).expanduser().resolve()) if key in PATH_KEYS else value
    for stale in ("filter_csv", "filter_column"):  # saved by earlier versions
        settings.pop(stale, None)
    settings.setdefault("impact", "label")
    settings.setdefault("include_fw_bot", False)

    # 1. PR list.
    if args.skip_fetch and paths["prs"].exists():
        fetched_at = datetime.fromtimestamp(paths["prs"].stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        say(f"Reusing PR list fetched {fetched_at}")
    else:
        say(f"Fetching PRs on {settings['repo']} {settings['branch']}")
        select = "" if settings["include_fw_bot"] else 'select(.user.login != "fw-bot") | '
        jq = (f".[] | {select}{{number, state, author: .user.login, created_at, merged_at, "
              "title, url: .html_url, body}")
        tmp = paths["prs"].with_suffix(".jsonl.tmp")
        with open(tmp, "w") as out:
            run(["gh", "api", f"repos/{settings['repo']}/pulls?state=all&base={settings['branch']}&per_page=100",
                 "--paginate", "--jq", jq], stdout=out)
        os.replace(tmp, paths["prs"])
        fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 2. Tasks. Covered tasks stay in: track_changes.py marks them instead.
    extract = script("extract_task_ids.py") + [str(paths["prs"]), "--require-task"]
    if not settings["include_fw_bot"]:
        extract += ["--exclude-author", "fw-bot"]
    with open(paths["rows"], "w") as out:
        say("Extracting tasks: " + run(extract, stdout=out))

    # 3. Documentation impact.
    scorer_version = None
    if settings["impact"] != "skip":
        say("Fetching diffs: " + run(script("fetch_pr_files.py") + [
            settings["repo"], str(paths["rows"]), "--output", str(paths["files"])]))
        score = script("score_doc_impact.py") + [str(paths["files"])]
        if settings.get("docs_repo"):
            ref = docs_ref(settings["docs_repo"], settings["branch"])
            score += ["--docs-repo", settings["docs_repo"], "--docs-ref", ref]
        with open(paths["impact"], "w") as out:
            summary = run(score, stdout=out)
        say("Scoring: " + summary)
        scorer_version = json.loads(summary).get("scorer_version")
        with open(paths["rows"], "w") as out:
            run(extract + ["--impact-jsonl", str(paths["impact"])], stdout=out)

    # 4. Tracked list.
    track = script("track_changes.py") + [
        str(paths["rows"]), "--state", str(paths["state"]), "--xlsx", str(paths["xlsx"]), "--csv", str(paths["csv"]),
        "--display", "label" if settings["impact"] == "skip" else settings["impact"],
        "--settings", json.dumps(settings), "--fetched-at", fetched_at,
    ]
    if args.filter_csv:
        track += ["--filter-csv", str(Path(args.filter_csv).expanduser().resolve()),
                  "--filter-column", args.filter_column or "RD Task ID"]
    if scorer_version:
        track += ["--scorer-version", scorer_version]
    if args.fresh:
        track.append("--fresh")
    result = json.loads(run(track))
    say("Tracked list updated")
    print(json.dumps(result | {"folder": str(folder), "csv": str(paths["csv"]),
                               "docs_ref": ref if settings["impact"] != "skip" and settings.get("docs_repo") else None}))


if __name__ == "__main__":
    main()
