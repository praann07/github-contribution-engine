#!/usr/bin/env python3
"""Pre-open revalidation. Run right before the PR is created (after the human's SHIP).

Reads docs/CYCLE.json (written by `audit.py cycle ...`). Checks, read-only, through ghx.py:
  1. IDEMPOTENCY: a PR from <fork_owner>:<branch> already exists -> exit 4 (adopt it, never create a second)
  2. the issue is still OPEN and not assigned to someone else
  3. no other open PR references the issue (competing work appeared)
  4. the base branch has not changed any file this fix touches (and warns if it moved at all)
On success writes docs/.revalidated, which gate.py requires (fresh, under 2 hours) before the PR is created.
Exit: 0 pass, 1 fail, 2 bad setup, 3 GitHub unreachable or auth/rate problem, 4 PR already opened.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ghx  # noqa: E402

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CYCLEF = os.path.join(ENGINE, "docs", "CYCLE.json")
OKF = os.path.join(ENGINE, "docs", ".revalidated")


def gh(args):
    rc, out, err, kind = ghx.run(args)
    if rc != 0:
        print(f"GitHub call failed ({kind}): gh {' '.join(args[:3])} ... {err.strip()[:160]}")
        if kind in ("transient", "auth", "rate_limit"):
            sys.exit(3)
        sys.exit(1)
    return out


def main():
    if os.path.exists(OKF):
        os.remove(OKF)
    try:
        c = json.load(open(CYCLEF, encoding="utf-8"))
    except Exception:
        print("docs/CYCLE.json missing or unreadable. Run: python scripts/audit.py cycle repo=... (see its --help).")
        return 2
    repo, issue, branch, owner = c["repo"], c["issue"], c["branch"], c["fork_owner"]
    base, base_sha, files = c["base"], c["base_sha"], set(c.get("files", []))
    fails, warns = [], []

    prs = json.loads(gh(["pr", "list", "--repo", repo, "--head", branch, "--state", "all",
                         "--json", "number,url,state,headRepositoryOwner"]) or "[]")
    mine = [p for p in prs if (p.get("headRepositoryOwner") or {}).get("login", "").lower() == owner.lower()]
    if mine:
        for p in mine:
            print(f"ALREADY OPENED: {p['url']} ({p['state']}). Do NOT create another. Log it: "
                  f"python scripts/audit.py log opened url={p['url']}")
        return 4

    iss = json.loads(gh(["issue", "view", str(issue), "--repo", repo, "--json", "state,assignees,title"]))
    if iss["state"] != "OPEN":
        fails.append(f"issue #{issue} is {iss['state']}")
    others = [a["login"] for a in iss.get("assignees", []) if a["login"].lower() != owner.lower()]
    if others:
        fails.append(f"issue #{issue} is now assigned to {', '.join(others)}")

    comp = json.loads(gh(["pr", "list", "--repo", repo, "--state", "open", "--search", f"#{issue}",
                          "--json", "number,url,author,headRefName", "--limit", "30"]) or "[]")
    comp = [p for p in comp if (p.get("author") or {}).get("login", "").lower() != owner.lower()]
    if comp:
        fails.append("competing open PR(s) mention #%d: %s" % (issue, ", ".join(p["url"] for p in comp)))

    cmp_ = json.loads(gh(["api", f"repos/{repo}/compare/{base_sha}...{base}", "--jq",
                          "{ahead: .ahead_by, files: [.files[].filename]}"]))
    touched = files & set(cmp_["files"])
    if touched:
        fails.append(f"{base} changed files this fix touches since scoping: {', '.join(sorted(touched))}. Rebase and retest.")
    if cmp_["ahead"]:
        warns.append(f"{base} moved by {cmp_['ahead']} commit(s) since scoping (no overlap with this fix).")

    for w in warns:
        print("WARN:", w)
    if fails:
        for f in fails:
            print("FAIL:", f)
        print("Not safe to open. Log the reason (audit.py log human_gate note=...) and tell the human.")
        return 1
    json.dump({"ts": time.time(), "cycle": f"{repo}#{issue}", "branch": branch}, open(OKF, "w"))
    print(f"revalidated OK for {repo}#{issue}; docs/.revalidated written (valid 2 hours).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
