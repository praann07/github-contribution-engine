#!/usr/bin/env python3
# gate.py - SINGLE source of gate logic. Tool-agnostic. Edited once; per-tool stubs never change.
#
# Modes (argv[1]):  bash (default) = a shell command arrives on stdin, either raw text or the
#                   Claude Code hook JSON {"tool_input": {"command": "..."}};  push = git pre-push hook.
# Exit 0 = allow, exit 2 = block (message on stderr).
#
# Human-owned artifacts the gate checks before anything leaves the machine:
#   docs/PR_BODY_DRAFT.md      PR body, shipped with --body-file
#   docs/COMMIT_MSG_DRAFT.md   the final pushed commit message (HEAD must match it)
# Sentinels: docs/.gate_open (reference hashes + timestamp), docs/.human_shipped (SHIP record).
import sys, os, json, hashlib, re, time, subprocess

ENGINE = os.path.dirname(os.path.abspath(__file__))
DOCS   = os.path.join(ENGINE, "docs")
BODYF  = os.path.join(DOCS, "PR_BODY_DRAFT.md")
COMMITF = os.path.join(DOCS, "COMMIT_MSG_DRAFT.md")
GATE   = os.path.join(DOCS, ".gate_open")
SHIP   = os.path.join(DOCS, ".human_shipped")
REVAL  = os.path.join(DOCS, ".revalidated")
REVAL_MAX_SECONDS = 2 * 3600              # scripts/revalidate.py must have passed within this window before a PR is created
HOLD_MAX_SECONDS = 7 * 24 * 3600          # a HOLD older than this must be aborted or re-opened
MARKERS = ("[SLOT:", "REFERENCE - REWRITE", "REFERENCE — REWRITE")


def _norm(p): return p.replace("\\", "/").rstrip("/")


def deny(msg):
    sys.stderr.write("BLOCKED by gate: " + msg + "\n"); sys.exit(2)


def _read_gate():
    try:
        return json.load(open(GATE))
    except Exception:
        deny(".gate_open unreadable - run python .claude/hooks/open_gate.py.")


def _human_text(path, ref_key, label, gate):
    """Return the human's text of `path` after checking it exists, changed from the reference, and has no markers."""
    if not os.path.exists(path): deny(os.path.basename(path) + " missing.")
    b = open(path, "rb").read()
    if not b.strip(): deny(os.path.basename(path) + " is empty - the human must write it.")
    if hashlib.sha256(b).hexdigest() == gate.get(ref_key, ""):
        deny(label + " byte-identical to reference - human must rewrite in own words.")
    t = b.decode("utf-8", "replace")
    if any(m in t for m in MARKERS): deny(label + " still has reference markers - finish the rewrite.")
    return t


def _shipped():
    if not os.path.exists(SHIP): deny("no .human_shipped - you are at stage 4; wait for the human's SHIP.")
    if not os.path.exists(GATE): deny(".gate_open missing - open_gate.py never ran this cycle.")
    gate = _read_gate()
    age = time.time() - float(gate.get("ts", 0))
    if age > HOLD_MAX_SECONDS:
        deny("gate is older than 7 days (HOLD expired) - run abort_cycle.py or re-run open_gate.py.")
    try:
        sent = json.load(open(SHIP))
    except Exception:
        sent = {}
    if not str(sent.get("defense", "")).strip():
        deny(".human_shipped has no DEFENSE line - the human's SHIP needs a non-empty DEFENSE=.")
    return gate, sent


def _revalidated():
    """A PR may only be created right after scripts/revalidate.py passed (issue open, no competitor, base not moved, no PR yet)."""
    try:
        ts = float(json.load(open(REVAL)).get("ts", 0))
    except Exception:
        deny("no fresh .revalidated - run python scripts/revalidate.py first (it also stops a duplicate PR after a crash).")
    if time.time() - ts > REVAL_MAX_SECONDS:
        deny(".revalidated is older than 2 hours - rerun python scripts/revalidate.py.")


def _body_ok():
    gate, sent = _shipped()
    return _human_text(BODYF, "ref_sha256", "body", gate), sent


def _squash(msg):
    """Compare commit messages ignoring trailing spaces, blank edges and DCO 'Signed-off-by:' trailers."""
    lines = [l.rstrip() for l in msg.replace("\r\n", "\n").split("\n") if not l.startswith("Signed-off-by:")]
    return "\n".join(lines).strip()


def _commit_ok():
    gate, _ = _shipped()
    want = _human_text(COMMITF, "commit_ref_sha256", "commit message", gate)
    r = subprocess.run(["git", "log", "-1", "--format=%B"], capture_output=True, text=True)
    if r.returncode != 0: deny("could not read HEAD commit message.")
    if _squash(r.stdout) != _squash(want):
        deny("HEAD commit message differs from docs/COMMIT_MSG_DRAFT.md - the final commit message is the human's.")


def _in_target_clone():
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    return _norm(top).startswith(_norm(os.path.join(ENGINE, "repos")) + "/")


def _api_write(command):
    if not (re.search(r"\bgh api\b", command) and "pulls" in command): return False
    return bool(re.search(r"(?:-X|--method)[= ]+\s*(POST|PATCH|PUT)\b", command, re.IGNORECASE))


def _command_from_stdin(raw):
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            d = json.loads(raw)
            return str((d.get("tool_input") or {}).get("command", ""))
        except Exception:
            return raw
    return raw


SECRET_PATTERNS = (
    r"\bgh auth (token|login|refresh|logout|setup-git|switch)\b",
    r"\bgh auth status\b.*(\s-t\b|--show-token)",
    r"\bgit credential\b|\bcmdkey\b",
    r"\b(GH_TOKEN|GITHUB_TOKEN|GH_ENTERPRISE_TOKEN|GITHUB_PAT)\b",
    r"hosts\.yml",
)


def cmd_bash(command):
    # Credentials never pass through model-written commands: no token printing, auth changes or credential stores.
    for pat in SECRET_PATTERNS:
        if re.search(pat, command, re.IGNORECASE):
            deny("credential access is human-only (token printing, gh auth changes, credential stores, token env vars).")
    # Human-only actions: the agent never publishes, merges, or comments.
    if re.search(r"\bgh pr (ready|merge|comment|review|close|reopen)\b", command):
        deny("human-only action - convert draft to ready, merge, comment and review are done by the human in GitHub.")
    if re.search(r"gh pr (create|edit)\b", command):          # PR open/edit: body gate + --body-file required
        _, sent = _body_ok()
        # any other way to supply a body (inline, -b, --fill, a second --body-file) could ship text the gate never read
        if re.search(r"(?<![\w-])(--body(?![-\w])|-b\b|--fill\b)", command):
            deny("inline --body / -b / --fill is not allowed; ship via --body-file only.")
        files = re.findall(r"(?:--body-file|-F)[= ]+(?:\"([^\"]+)\"|'([^']+)'|(\S+))", command)
        if len(files) != 1: deny("must ship via exactly one --body-file pointing at the absolute path of docs/PR_BODY_DRAFT.md.")
        # ABSOLUTE path only: a relative path would be read by gh from the shell's cwd, which the hook cannot see,
        # so the file gh reads could differ from the file checked here. Quoted paths may contain spaces.
        path = next(g for g in files[0] if g)
        if not os.path.isabs(path):
            deny("--body-file must be the ABSOLUTE path to docs/PR_BODY_DRAFT.md (relative paths are ambiguous).")
        if os.path.normcase(os.path.realpath(path)) != os.path.normcase(os.path.realpath(BODYF)):
            deny("--body-file must point exactly at PR_BODY_DRAFT.md.")
        if re.search(r"gh pr create\b", command):
            _revalidated()
            wants_draft = bool(sent.get("draft"))
            has_draft = bool(re.search(r"(?<![\w-])--draft\b", command))
            if wants_draft and not has_draft: deny("the human shipped SHIP DRAFT - add --draft.")
            if has_draft and not wants_draft: deny("--draft was not requested; plain SHIP opens a live PR.")
        sys.exit(0)
    if _api_write(command):
        _body_ok()
        if re.search(r"(?:-X|--method)[= ]+\s*POST\b", command, re.IGNORECASE): _revalidated()
        sys.exit(0)           # API-only PR-open bypass (POST/PATCH/PUT)
    if re.search(r"\bgit push\b", command) and _in_target_clone():   # push inside a target clone
        _body_ok(); _commit_ok(); sys.exit(0)
    sys.exit(0)                                               # GET read-backs + everything else: allow


def cmd_push():
    if not _in_target_clone(): sys.exit(0)                    # not a target clone -> no-op
    _body_ok(); _commit_ok(); sys.exit(0)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "bash"
    if mode == "push": cmd_push()
    else: cmd_bash(_command_from_stdin(sys.stdin.read()))
