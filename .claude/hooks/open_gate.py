#!/usr/bin/env python3
# Stage 4 (d): record the REFERENCE hashes of the two human-owned files, then the agent stops.
import os, json, hashlib, time
HERE   = os.path.dirname(os.path.abspath(__file__))      # .../ENGINE/.claude/hooks
ENGINE = os.path.dirname(os.path.dirname(HERE))          # .../ENGINE
body   = os.path.join(ENGINE, "docs", "PR_BODY_DRAFT.md")
commit = os.path.join(ENGINE, "docs", "COMMIT_MSG_DRAFT.md")
for p in (body, commit):
    if not os.path.exists(p):
        raise SystemExit("open_gate: " + os.path.relpath(p, ENGINE) + " missing - write the reference first.")
h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
json.dump({"ref_sha256": h(body), "commit_ref_sha256": h(commit), "ts": time.time()},
          open(os.path.join(ENGINE, "docs", ".gate_open"), "w"))
print("gate_open recorded; body ref=", h(body)[:12], " commit ref=", h(commit)[:12])
