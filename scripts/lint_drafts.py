#!/usr/bin/env python3
"""Advisory lint for the human's draft files before SHIP. Never edits anything. Exit 1 if anything is flagged."""
import os
import re
import sys

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ENGINE, "docs")
MARKERS = ("[SLOT:", "REFERENCE - REWRITE", "REFERENCE — REWRITE")


def lint_body(t):
    out = []
    if any(m in t for m in MARKERS):
        out.append("still has a reference marker / [SLOT:] - the gate will block it")
    if not re.search(r"^(Closes|Fixes|Resolves) #\d+\s*$", t, re.M | re.I):
        out.append("no 'Closes #N' / 'Fixes #N' alone on its own line")
    for i, line in enumerate(t.splitlines(), 1):
        if re.search(r"\S.*\s##\s", line):
            out.append(f"line {i}: a '## heading' is stuck to other text")
        if re.search(r"\]\([^)]*\)[A-Za-z]", line):
            out.append(f"line {i}: missing space after a markdown link")
        if re.search(r"\w  +\w", line.strip()):
            out.append(f"line {i}: double space")
        if line != line.rstrip():
            out.append(f"line {i}: trailing space")
        if re.search(r"(…|\.\.\.)", line):
            out.append(f"line {i}: ellipsis - leftover fragment?")
    if t.count("`") % 2:
        out.append("odd number of backticks (unclosed code span?)")
    if t.count("(") != t.count(")"):
        out.append("unbalanced parentheses")
    if t.count("[") != t.count("]"):
        out.append("unbalanced square brackets")
    m = re.search(r"(?<=[.!?] )[a-z]\w*", t)
    if m:
        out.append("a sentence may start in lowercase near: " + t[m.start():m.start() + 25].replace("\n", " "))
    return out


def lint_commit(t):
    out = []
    if any(m in t for m in MARKERS):
        out.append("still has a reference marker / [SLOT:]")
    lines = t.strip().splitlines()
    first = lines[0] if lines else ""
    if not re.match(r"^[a-z]+(\([\w./-]+\))?!?: \S", first):
        out.append("title is not 'type(scope): summary'")
    if len(first) > 100:
        out.append("title is longer than 100 characters")
    if len(lines) > 1 and lines[1].strip():
        out.append("no blank line after the title")
    return out


def main():
    bad = 0
    for name, fn in (("PR_BODY_DRAFT.md", lint_body), ("COMMIT_MSG_DRAFT.md", lint_commit)):
        p = os.path.join(DOCS, name)
        if not os.path.exists(p):
            print(name, "- missing")
            bad += 1
            continue
        issues = fn(open(p, encoding="utf-8").read())
        print(name, "- OK" if not issues else f"- {len(issues)} thing(s) to look at")
        for i in issues:
            print("   *", i)
        bad += bool(issues)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
