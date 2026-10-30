#!/usr/bin/env python3
"""Read-only multi-repo scout (stage 1, gh only, no clone).

usage: python scripts/scout.py owner/repo [owner/repo ...]

For each repo: good-first-issue / help-wanted / ready-for-dev counts, open PR count, and open bug-ish issues that
are unassigned AND not mentioned by any open PR, newest first. Output is a shortlist for the human to approve by name.
It never writes to GitHub and never edits docs/TARGETS.md.
"""
import json
import re
import subprocess
import sys

LABELS = ("good first issue", "help wanted", "ready-for-dev", "bug", "🐞 bug", "type: bug")


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=180)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return json.loads(r.stdout or "[]")


def scout(repo):
    meta = gh("repo", "view", repo, "--json", "nameWithOwner,primaryLanguage,pushedAt,isArchived")
    print(f"\n== {meta['nameWithOwner']} ({(meta.get('primaryLanguage') or {}).get('name')}), "
          f"pushed {meta['pushedAt'][:10]}{' ARCHIVED' if meta['isArchived'] else ''}")
    prs = gh("pr", "list", "--repo", repo, "--state", "open", "--limit", "1000", "--json", "number,title,body")
    mentioned = set()
    for p in prs:
        mentioned |= {int(n) for n in re.findall(r"#(\d{2,6})", (p["title"] or "") + " " + (p["body"] or ""))}
    counts, cands = {}, {}
    for lab in LABELS:
        try:
            iss = gh("issue", "list", "--repo", repo, "--label", lab, "--state", "open", "--limit", "200",
                     "--json", "number,title,assignees,createdAt,comments")
        except RuntimeError:
            continue
        counts[lab] = len(iss)
        for i in iss:
            if not i["assignees"] and i["number"] not in mentioned:
                cands[i["number"]] = (i["createdAt"][:10], len(i["comments"]), i["title"][:80], lab)
    print("   labels:", ", ".join(f"{k}={v}" for k, v in counts.items() if v) or "none",
          f"| open PRs={len(prs)}")
    free = sorted(cands.items(), key=lambda kv: kv[1][0], reverse=True)[:8]
    if not free:
        print("   no unassigned, unmentioned labelled issues -> likely NO_VALID_TARGET")
    for n, (d, c, t, lab) in free:
        print(f"   #{n} {d} c={c} [{lab}] {t}")


def main(repos):
    if not repos:
        print(__doc__)
        return 2
    for r in repos:
        try:
            scout(r)
        except Exception as e:  # keep scanning the rest
            print(f"\n== {r}: ERROR {e}")
    print("\nNext: verify each candidate by hand (comments, closed PRs, policy files) before asking the human.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
