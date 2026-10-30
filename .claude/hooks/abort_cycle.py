#!/usr/bin/env python3
# Human says ABORT <reason> at AWAITING_HUMAN: leave the gate locked and the workspace clean.
# Usage: python .claude/hooks/abort_cycle.py "<reason>"
# Removes the sentinels, empties the per-cycle drafts, appends the reason to docs/LOG.md, sets cursor IDLE.
# It never touches GitHub and never deletes the local branch (no work is lost).
import os, sys, time, re
HERE   = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(os.path.dirname(HERE))
D = os.path.join(ENGINE, "docs")
reason = " ".join(sys.argv[1:]).strip()
if not reason: raise SystemExit("abort_cycle: give a reason, e.g. abort_cycle.py \"too risky\"")
for name in (".gate_open", ".human_shipped"):
    p = os.path.join(D, name)
    if os.path.exists(p): os.remove(p)
for name in ("PR_BODY_DRAFT.md", "COMMIT_MSG_DRAFT.md", "HUMAN_GATE.md"):
    open(os.path.join(D, name), "w").close()
with open(os.path.join(D, "LOG.md"), "a", encoding="utf-8") as f:
    f.write(time.strftime("%Y-%m-%d") + " ABORTED at AWAITING_HUMAN: " + reason + "\n")
sp = os.path.join(D, "STATE.md")
s = open(sp, encoding="utf-8").read()
s = re.sub(r"(?m)^cursor:.*$", "cursor: IDLE", s, count=1)
s = re.sub(r"(?m)^awaiting_human:.*$", "awaiting_human: no", s, count=1)
open(sp, "w", encoding="utf-8").write(s)
print("aborted; gate locked; cursor IDLE; local branch kept")
