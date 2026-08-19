#!/usr/bin/env python3
"""
rst_meta.py — deterministic helpers for the rst-meta-description skill.

Two subcommands:

  analyze <file>
      Reads the file and reports (as JSON):
        - state: "missing" | "bare_field" | "proper_meta"
        - existing_description: current description text, if any
        - candidate_points: list of short candidate "things to highlight",
          extracted from headings and the first sentence following each
          one. This is pattern-matching only — no summarization judgment.

  write <file> --description "TEXT"
      Given a final description (already written by the model), performs
      all the mechanical work:
        - removes a bare ":description:" docinfo field if present
        - removes an existing ".. meta::" description field if present
          (so regeneration replaces rather than duplicates)
        - wraps TEXT to a max of 100 chars/line using RST multi-line
          field-body continuation syntax
        - inserts the new ".. meta::" block at the very top of the file
        - writes the file in place

Nothing in this script decides *what* the description should say — that
judgment stays with the model. This script only handles detection,
extraction of raw candidate material, formatting, and file I/O.
"""

import argparse
import json
import re
import sys


MAX_LINE_WIDTH = 100
FIELD_INDENT = "   "        # indent for the field name under ".. meta::"
# Continuation indent is computed dynamically in wrap_field_body() to match
# the width of "<FIELD_INDENT>:description: " exactly, so wrapped lines
# hang-indent flush under the start of the description text rather than
# sitting at a fixed, shallower indent.


# ---------- detection ----------

def find_bare_field_span(text):
    """
    Detect a bare docinfo-style ':description:' field list at the top of
    the file (the common RST mistake: renders visibly instead of going
    into <head>). Returns (start, end) char offsets to remove, or None.
    """
    # Bare field lists must appear before any content/title, only preceded
    # by blank lines or comments. Look at the leading run of lines.
    lines = text.splitlines(keepends=True)
    idx = 0
    offset = 0
    field_start_offset = None
    field_end_offset = None
    in_field = False

    for line in lines:
        stripped = line.strip()
        if not in_field:
            if stripped == "" or stripped.startswith(".."):
                offset += len(line)
                idx += 1
                continue
            m = re.match(r"^:description:(\s*.*)$", line)
            if m:
                in_field = True
                field_start_offset = offset
                offset += len(line)
                idx += 1
                continue
            else:
                # First substantive line isn't a bare description field —
                # no bare field list to remove.
                break
        else:
            # Inside the field body: continuation lines are indented;
            # a blank line or an unindented line ends the field.
            if stripped == "":
                field_end_offset = offset
                break
            if line.startswith(" ") or line.startswith("\t"):
                offset += len(line)
                idx += 1
                continue
            else:
                field_end_offset = offset
                break

    if field_start_offset is not None:
        if field_end_offset is None:
            field_end_offset = offset
        return (field_start_offset, field_end_offset)
    return None


def find_proper_meta_description(text):
    """
    Detect an existing '.. meta::' directive with a ':description:' field.
    Returns (start, end, existing_text) or None. start/end bound the whole
    directive block (so it can be replaced wholesale on regeneration).
    """
    pattern = re.compile(
        r"^\.\. meta::\n((?:[ \t]+.*\n?)+)",
        re.MULTILINE,
    )
    m = pattern.search(text)
    if not m:
        return None
    block = m.group(0)
    desc_match = re.search(
        r":description:\s*(.*(?:\n[ \t]+\S.*)*)", block
    )
    existing_desc = None
    if desc_match:
        raw = desc_match.group(1)
        # collapse continuation-line wrapping back into one string
        existing_desc = re.sub(r"\s*\n\s*", " ", raw).strip()
    return (m.start(), m.end(), existing_desc)


def detect_state(text):
    proper = find_proper_meta_description(text)
    if proper:
        return "proper_meta", proper[2]
    bare = find_bare_field_span(text)
    if bare:
        bare_text = text[bare[0]:bare[1]]
        m = re.match(r"^:description:\s*(.*)$", bare_text, re.DOTALL)
        existing = None
        if m:
            existing = re.sub(r"\s*\n\s*", " ", m.group(1)).strip()
        return "bare_field", existing
    return "missing", None


# ---------- candidate extraction (pattern-matching only) ----------

UNDERLINE_CHARS = set("=-~^\"'`#*+.:_")


def extract_headings_with_intro(text):
    """
    Extract RST section titles (title line followed by a matching
    underline of repeated punctuation) plus the first sentence of the
    paragraph immediately following each one. Pure pattern-matching —
    no interpretation of meaning.
    """
    lines = text.splitlines()
    results = []
    i = 0
    n = len(lines)

    def is_underline(line, title_len):
        s = line.strip()
        if len(s) < 1:
            return False
        if len(set(s)) != 1:
            return False
        if s[0] not in UNDERLINE_CHARS:
            return False
        return len(s) >= max(title_len, 1)

    while i < n - 1:
        title_line = lines[i].strip()
        next_line = lines[i + 1]
        if title_line and is_underline(next_line, len(title_line)):
            # find first non-empty paragraph after the underline
            j = i + 2
            while j < n and lines[j].strip() == "":
                j += 1
            para_lines = []
            while j < n and lines[j].strip() != "" and not (
                j + 1 < n and is_underline(lines[j + 1], len(lines[j].strip()))
            ):
                para_lines.append(lines[j].strip())
                j += 1
            para_text = " ".join(para_lines)
            first_sentence = re.split(r"(?<=[.!?])\s+", para_text.strip())
            first_sentence = first_sentence[0] if first_sentence else ""
            results.append({
                "heading": title_line,
                "first_sentence": first_sentence[:200],
            })
            i = j
        else:
            i += 1
    return results


def extract_intro_sentence(text, headings):
    """First sentence of the page's intro paragraph (before the first
    subsection, i.e. right after the H1)."""
    if not headings:
        return None
    lines = text.splitlines()
    # crude: text between end of first heading block and start of next
    # heading; reuse extract_headings_with_intro's first entry, which
    # already captured the first paragraph after the title.
    return headings[0]["first_sentence"] if headings else None


# ---------- formatting / writing ----------

def wrap_field_body(description, width=MAX_LINE_WIDTH):
    """
    Wrap description text into RST multi-line field-body lines, each
    within `width` characters including indentation. Continuation lines
    use a hanging indent equal to the width of "<FIELD_INDENT>:description: "
    so wrapped text aligns flush under the start of the description on the
    first line, e.g.:

        :description: Explains how to schedule and manage activities from a record's chatter,
                       Kanban, list, or Activity view, ...
    """
    prefix = f"{FIELD_INDENT}:description: "
    cont_indent = " " * len(prefix)
    words = description.split()
    lines = []
    current = prefix
    for word in words:
        candidate = current + word + " "
        line_has_content = current not in (prefix, cont_indent)
        if len(candidate.rstrip()) > width and line_has_content:
            lines.append(current.rstrip())
            current = cont_indent + word + " "
        else:
            current = candidate
    if current.strip():
        lines.append(current.rstrip())
    return lines


def build_meta_block(description):
    body_lines = wrap_field_body(description)
    block_lines = [".. meta::"] + body_lines
    return "\n".join(block_lines) + "\n\n"


def remove_existing_description_markup(text):
    """Strip out a bare field or an existing proper meta block, returning
    cleaned text ready for a fresh block to be prepended."""
    proper = find_proper_meta_description(text)
    if proper:
        start, end, _ = proper
        text = text[:start] + text[end:]
        # collapse resulting blank-line runs at the very top
        text = re.sub(r"^\s*\n+", "", text)
        return text
    bare = find_bare_field_span(text)
    if bare:
        start, end = bare
        text = text[:start] + text[end:]
        text = re.sub(r"^\s*\n+", "", text)
        return text
    return text


def write_description(path, description):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    cleaned = remove_existing_description_markup(text)
    block = build_meta_block(description)
    new_text = block + cleaned
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    return new_text[:len(block)]


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    ap_analyze = sub.add_parser("analyze")
    ap_analyze.add_argument("file")

    ap_write = sub.add_parser("write")
    ap_write.add_argument("file")
    ap_write.add_argument("--description", required=True)

    args = ap.parse_args()

    if args.command == "analyze":
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
        state, existing_description = detect_state(text)
        headings = extract_headings_with_intro(text)
        candidate_points = []
        intro = extract_intro_sentence(text, headings)
        if intro:
            candidate_points.append({"label": "Page intro", "text": intro})
        for h in headings[1:] if headings else []:
            if h["first_sentence"]:
                candidate_points.append({
                    "label": h["heading"],
                    "text": h["first_sentence"],
                })
        result = {
            "state": state,
            "existing_description": existing_description,
            "headings": [h["heading"] for h in headings],
            "candidate_points": candidate_points,
        }
        print(json.dumps(result, indent=2))

    elif args.command == "write":
        block_written = write_description(args.file, args.description)
        print(json.dumps({
            "status": "written",
            "file": args.file,
            "block": block_written.strip(),
        }, indent=2))


if __name__ == "__main__":
    main()
