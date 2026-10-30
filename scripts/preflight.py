#!/usr/bin/env python3
"""Cycle preflight: stop early if GitHub is unreachable instead of burning retries. Exit 0 = ok, 3 = offline."""
import subprocess
import sys


def main():
    try:
        r = subprocess.run(["gh", "api", "rate_limit", "--jq", ".rate.remaining"],
                           capture_output=True, text=True, timeout=25)
    except subprocess.TimeoutExpired:
        r = None
    if r is not None and r.returncode == 0 and r.stdout.strip().isdigit():
        print("preflight ok: GitHub reachable, rate remaining", r.stdout.strip())
        return 0
    print("preflight FAILED: GitHub unreachable from this shell (VPN/proxy/campus block?). "
          "Fix the network, then rerun. No stage was started.")
    return 3


if __name__ == "__main__":
    sys.exit(main())
