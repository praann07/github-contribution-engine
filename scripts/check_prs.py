#!/usr/bin/env python3
"""(add --log to append a CI line to docs/audit.jsonl)
One-command read-back of every PR in docs/WATCH.txt (gh only, read-only). Say "check" and run this.

docs/WATCH.txt: one `owner/repo#number` per line. Lines starting with # are ignored.
Per PR it prints reviewDecision, mergeStateStatus, checks, and who commented/reviewed (bot vs human).
Bot reviews are NOT human sign-off (see docs/PR_CHECKPOINTS.md); this script never replies or pushes.
"""
import json
import os
import re
import subprocess
import sys

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_HINTS = ("bot", "coderabbit", "copilot", "vercel", "github-actions", "dependabot", "machine", "codecov", "sonar")


def main():
    path = os.path.join(ENGINE, "docs", "WATCH.txt")
    if not os.path.exists(path):
        print("docs/WATCH.txt missing")
        return 2
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        m = re.match(r"^([\w.-]+/[\w.-]+)#(\d+)$", line)
        if not m:
            continue
        repo, n = m.groups()
        r = subprocess.run(["gh", "pr", "view", n, "--repo", repo, "--json",
                            "state,isDraft,reviewDecision,mergeStateStatus,statusCheckRollup,reviews,comments,url"],
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
        if r.returncode != 0:
            print(f"{repo}#{n}: ERROR {r.stderr.strip()[:150]}")
            continue
        d = json.loads(r.stdout)
        checks = [f"{c.get('name') or c.get('context')}:{c.get('conclusion') or c.get('state') or c.get('status')}"
                  for c in d["statusCheckRollup"] or []]
        people = [(x["author"]["login"], x["state"]) for x in d["reviews"]]
        commenters = sorted({c["author"]["login"] for c in d["comments"]})
        human = [p for p in people if not any(b in p[0].lower() for b in BOT_HINTS)]
        print(f"\n{repo}#{n} {d['state']}{' DRAFT' if d['isDraft'] else ''}  {d['url']}")
        print(f"   reviewDecision={d['reviewDecision'] or '-'}  mergeState={d['mergeStateStatus']}")
        bad, wait, good = [], [], 0
        for c in d["statusCheckRollup"] or []:
            nm = c.get("name") or c.get("context")
            st = (c.get("conclusion") or c.get("state") or c.get("status") or "").upper()
            if st in ("SUCCESS", "NEUTRAL", "SKIPPED"): good += 1
            elif st in ("FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"): bad.append(nm)
            else: wait.append(nm)
        print(f"   CI: {good} pass, {len(wait)} pending, {len(bad)} failing")
        if bad: print("   failing:", ", ".join(bad), "(maintainer-side checks like Label Checker or deploy approval are not your code)")
        if wait: print("   pending:", ", ".join(wait))
        if "--log" in sys.argv:
            subprocess.run([sys.executable, os.path.join(ENGINE, "scripts", "audit.py"), "log", "ci",
                            f"pr={repo}#{n}", f"pass={good}", f"pending={len(wait)}", f"failing={len(bad)}"], check=False)
        print("   human reviews:", human or "none yet", "| commenters:", ", ".join(commenters) or "none")
        if human:
            print("   >> a HUMAN has reviewed: read it on GitHub and tell me; I will not reply for you.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
