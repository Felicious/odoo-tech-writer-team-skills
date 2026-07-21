#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Given one or more GitHub PR URLs or numbers (odoo/odoo repo), fetch each PR body
via gh CLI and extract the task-XXXXXXX pattern.

Usage:
  pr_to_task.py <pr1> [pr2 ...]             # human-readable output
  pr_to_task.py --json <pr1> [pr2 ...]      # JSON array output for scripting
"""
import json
import re
import subprocess
import sys

BASE_TASK_URL = "https://www.odoo.com/odoo/project/19060/tasks/"


def extract_pr_number(pr_input):
    match = re.search(r"/pull/(\d+)", pr_input)
    if match:
        return match.group(1)
    if pr_input.strip().isdigit():
        return pr_input.strip()
    return None


def get_pr_data(pr_number):
    result = subprocess.run(
        ["gh", "pr", "view", pr_number, "--repo", "odoo/odoo", "--json", "body,title,url"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def extract_task_id(body):
    patterns = [
        r"task-id-(\d+)",                 # task-id-1234567
        r"task-(\d+)",                    # task-1234567 / Task-1234567
        r"task\s*:\s*(\d+)",              # Task: 1234567 / task: 1234567
        r"task\s+id\s*:?\s*\[?(\d+)",    # Task ID: [1234567] / Task Id: 1234567
    ]
    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def process(pr_inputs):
    results = []
    for pr_input in pr_inputs:
        pr_number = extract_pr_number(pr_input)
        if not pr_number:
            results.append({"input": pr_input, "error": "could not parse PR number"})
            continue

        data = get_pr_data(pr_number)
        if not data:
            results.append({"pr_number": pr_number, "error": "gh cli fetch failed"})
            continue

        body = data.get("body", "")
        task_id = extract_task_id(body)
        results.append({
            "pr_number": pr_number,
            "pr_url": data.get("url", ""),
            "title": data.get("title", ""),
            "task_id": task_id,
            "task_url": f"{BASE_TASK_URL}{task_id}" if task_id else None,
            "body_excerpt": body[:1500].strip() if not task_id else None,
        })
    return results


def main():
    args = sys.argv[1:]
    json_mode = "--json" in args
    if json_mode:
        args = [a for a in args if a != "--json"]

    if not args:
        print("Usage: pr_to_task.py [--json] <pr_url_or_number> [...]")
        sys.exit(1)

    results = process(args)

    if json_mode:
        print(json.dumps(results, indent=2))
        return

    for r in results:
        if "error" in r:
            print(f"\nERROR ({r.get('input') or r.get('pr_number')}): {r['error']}")
            continue
        print(f"\nPR #{r['pr_number']}: {r['title']}")
        print(f"  PR URL:   {r['pr_url']}")
        if r["task_url"]:
            print(f"  Task URL: {r['task_url']}")
        else:
            print("  Task URL: NOT FOUND — no task-XXXXXXX in PR body")
            print("  --- PR body excerpt ---")
            print(f"  {r['body_excerpt']}")
            print("  --- end ---")


if __name__ == "__main__":
    main()
