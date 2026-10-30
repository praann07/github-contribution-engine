#!/usr/bin/env python3
"""Structured audit log + crash-safe resume for the engine.

  python scripts/audit.py cycle repo=O/R issue=N branch=B fork_owner=U base=develop base_sha=SHA files=a,b
        write docs/CYCLE.json (the plan that revalidate.py checks) and log a `scope` event
  python scripts/audit.py log STAGE key=value ...
        append one JSON line to docs/audit.jsonl (ts and cycle are added). Stages in order:
        preflight scope draft local_gate human_gate ship open_started opened recorded ci
        Useful keys: sha=<commit> tests="9 passed" approval=SHIP url=<pr url> note=...
  python scripts/audit.py resume
        read the last event of the current cycle and say what is safe to do next
  python scripts/audit.py show [N]     print the last N events (default 15)

The cursor in docs/STATE.md says where the engine is; this file says what actually happened and is
append-only, so a crash or restart can never repeat a stage blindly.
"""
import json
import os
import sys
import time

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGF = os.path.join(ENGINE, "docs", "audit.jsonl")
CYCLEF = os.path.join(ENGINE, "docs", "CYCLE.json")
STAGES = ["preflight", "scope", "draft", "local_gate", "human_gate", "ship", "open_started", "opened", "recorded", "ci"]
NEXT = {
    "preflight": "scope: run the stage 1 scan.",
    "scope": "draft: clone, fix, test (stage 2-3).",
    "draft": "local_gate: run the tests and linters (stage 3).",
    "local_gate": "human_gate: write the reference drafts, run open_gate.py, set the cursor AWAITING_HUMAN, STOP.",
    "human_gate": "WAIT. Only the human's literal SHIP moves this on.",
    "ship": "revalidate: run python scripts/revalidate.py, then open the PR.",
    "open_started": "A crash may have happened mid-open. Run python scripts/revalidate.py: it detects an "
                    "already-open PR and exits 4 (do NOT create a second one; log `opened` with its url).",
    "opened": "record: update docs/GATES.md, STATE.md, LOG.md, DASHBOARD.md, WATCH.txt; delete the sentinels.",
    "recorded": "ci: run python scripts/check_prs.py and log the CI result. Then wait for maintainers.",
    "ci": "WAIT for maintainers (python scripts/check_prs.py). Idle until the human asks or approves a new repo.",
}


def cycle_id():
    try:
        c = json.load(open(CYCLEF, encoding="utf-8"))
        return f"{c['repo']}#{c['issue']}"
    except Exception:
        return "-"


def append(stage, fields):
    ev = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "cycle": cycle_id(), "stage": stage}
    ev.update(fields)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=True) + "\n")
    return ev


def events():
    if not os.path.exists(LOGF):
        return []
    out = []
    for line in open(LOGF, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def kv(args):
    d = {}
    for a in args:
        k, _, v = a.partition("=")
        d[k] = v
    return d


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "cycle":
        d = kv(rest)
        need = ("repo", "issue", "branch", "fork_owner", "base", "base_sha")
        miss = [k for k in need if not d.get(k)]
        if miss:
            print("missing:", ", ".join(miss))
            return 2
        d["issue"] = int(d["issue"])
        d["files"] = [f for f in d.get("files", "").split(",") if f]
        json.dump(d, open(CYCLEF, "w", encoding="utf-8"), indent=2)
        append("scope", {k: d[k] for k in ("repo", "issue", "branch", "base_sha")})
        print("CYCLE.json written; scope logged")
        return 0
    if cmd == "log":
        if not rest or rest[0] not in STAGES:
            print("stage must be one of:", " ".join(STAGES))
            return 2
        ev = append(rest[0], kv(rest[1:]))
        print("logged:", json.dumps(ev))
        return 0
    if cmd == "show":
        n = int(rest[0]) if rest else 15
        for e in events()[-n:]:
            print(json.dumps(e))
        return 0
    if cmd == "resume":
        cyc = cycle_id()
        evs = [e for e in events() if e.get("cycle") == cyc]
        if not evs:
            print(f"cycle {cyc}: no events. Start at preflight.")
            return 0
        last = evs[-1]
        print(f"cycle {cyc}: last stage = {last['stage']} at {last['ts']}")
        print("next:", NEXT.get(last["stage"], "unknown stage"))
        print("also: read docs/STATE.md cursor; if it disagrees with this log, trust the log and fix STATE.md.")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
