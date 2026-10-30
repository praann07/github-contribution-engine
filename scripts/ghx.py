#!/usr/bin/env python3
"""gh wrapper with a timeout and a failure classifier. Import `run`, or: python scripts/ghx.py <gh args...>

Kinds: ok | rate_limit | auth | transient | permanent.
Only `transient` is retried (backoff 2s, 5s, 12s). rate_limit, auth and permanent stop at once so a
real problem is reported instead of hammered. Read-only use; callers decide what to run.
"""
import re
import subprocess
import sys
import time

BACKOFF = (2, 5, 12)
TRANSIENT = re.compile(r"timed out|timeout|connectex|forcibly closed|connection reset|EOF|HTTP 50[234]|"
                       r"temporarily unavailable|TLS handshake|no such host", re.I)
RATE = re.compile(r"rate limit|secondary rate|abuse detection|HTTP 429", re.I)
AUTH = re.compile(r"HTTP 401|bad credentials|authentication|not logged in|gh auth login|requires authentication", re.I)


def classify(rc, text):
    if rc == 0:
        return "ok"
    if RATE.search(text):
        return "rate_limit"
    if AUTH.search(text):
        return "auth"
    if TRANSIENT.search(text):
        return "transient"
    return "permanent"


def run(args, retries=3, timeout=45):
    """Run `gh <args>`. Returns (returncode, stdout, stderr, kind)."""
    last = (1, "", "", "permanent")
    for attempt in range(retries + 1):
        try:
            r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=timeout)
            rc, out, err = r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired:
            rc, out, err = 124, "", "timed out"
        kind = classify(rc, err + out)
        last = (rc, out, err, kind)
        if kind != "transient" or attempt == retries:
            return last
        time.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
    return last


if __name__ == "__main__":
    rc, out, err, kind = run(sys.argv[1:])
    sys.stdout.write(out)
    sys.stderr.write(err)
    print(f"[ghx] kind={kind}", file=sys.stderr)
    sys.exit(rc)
