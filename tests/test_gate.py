"""Tests for gate.py. Each test builds a throwaway engine in tmp_path, so the real gate is never touched."""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REAL_GATE = Path(__file__).resolve().parent.parent / "gate.py"
REFERENCE_BODY = "REFERENCE — REWRITE IN YOUR OWN WORDS\n[SLOT: why]\n"
REFERENCE_COMMIT = "REFERENCE — REWRITE IN YOUR OWN WORDS\n[SLOT: subject]\n"
HUMAN_BODY = "Fixes the hang when the server stalls.\n"
HUMAN_COMMIT = "fix: add a request timeout\n"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def engine(tmp_path: Path) -> Path:
    """A fresh engine with a gate.py copy, docs/, and a target clone under repos/."""
    (tmp_path / "docs").mkdir()
    shutil.copy(REAL_GATE, tmp_path / "gate.py")
    clone = tmp_path / "repos" / "o__r"
    clone.mkdir(parents=True)
    git(clone, "init", "-q")
    git(clone, "config", "user.email", "t@t")
    git(clone, "config", "user.name", "t")
    (clone / "f.txt").write_text("x")
    git(clone, "add", "f.txt")
    git(clone, "commit", "-q", "-m", HUMAN_COMMIT.strip())
    return tmp_path


def run(engine: Path, mode: str, stdin: str = "", cwd: Path | None = None):
    # "{BODY}" stands for the quoted ABSOLUTE path of this engine's PR_BODY_DRAFT.md (the gate accepts only that form)
    stdin = stdin.replace("{BODY}", '\\"' + (engine / "docs" / "PR_BODY_DRAFT.md").as_posix() + '\\"'
                          if stdin.lstrip().startswith("{") else '"' + (engine / "docs" / "PR_BODY_DRAFT.md").as_posix() + '"')
    return subprocess.run(
        [sys.executable, str(engine / "gate.py"), mode],
        input=stdin, capture_output=True, text=True, cwd=cwd or engine,
    )


def open_cycle(engine: Path, *, draft: bool = False, defense: str = "it is right", age: float = 0.0,
               body: str = HUMAN_BODY, commit: str = HUMAN_COMMIT, revalidated_age: float | None = 0.0) -> None:
    """Simulate stages 4-5: references recorded, the human rewrote both files and typed SHIP.
    revalidated_age: seconds since scripts/revalidate.py passed; None = it never ran."""
    d = engine / "docs"
    if revalidated_age is not None:
        (d / ".revalidated").write_text(json.dumps({"ts": time.time() - revalidated_age}))
    (d / ".gate_open").write_text(json.dumps({
        "ref_sha256": sha(REFERENCE_BODY), "commit_ref_sha256": sha(REFERENCE_COMMIT), "ts": time.time() - age}))
    (d / ".human_shipped").write_text(json.dumps({"cycle": 1, "defense": defense, "draft": draft, "ts": 0}))
    (d / "PR_BODY_DRAFT.md").write_text(body, encoding="utf-8")
    (d / "COMMIT_MSG_DRAFT.md").write_text(commit, encoding="utf-8")


CREATE = "gh pr create --repo o/r --title T --body-file {BODY}"


# ---- locked by default -------------------------------------------------------------------------
def test_pr_create_blocked_without_ship(engine):
    r = run(engine, "bash", CREATE)
    assert r.returncode == 2 and "human_shipped" in r.stderr


def test_unrelated_commands_allowed(engine):
    assert run(engine, "bash", "gh pr view 5 --repo o/r --json state").returncode == 0
    assert run(engine, "bash", "git status").returncode == 0


def test_push_outside_target_clone_is_noop(engine, tmp_path):
    other = tmp_path.parent / "elsewhere_repo"
    other.mkdir(exist_ok=True)
    git(other, "init", "-q")
    assert run(engine, "push", cwd=other).returncode == 0


# ---- the happy path ----------------------------------------------------------------------------
def test_live_ship_allows_pr_create_and_push(engine):
    open_cycle(engine)
    assert run(engine, "bash", CREATE).returncode == 0
    assert run(engine, "push", cwd=engine / "repos" / "o__r").returncode == 0


def test_claude_code_json_input_is_understood(engine):
    open_cycle(engine)
    payload = json.dumps({"tool_input": {"command": CREATE}})
    assert run(engine, "bash", payload).returncode == 0
    bad = json.dumps({"tool_input": {"command": "gh pr create --title T --body 'inline'"}})
    assert run(engine, "bash", bad).returncode == 2


# ---- body rules --------------------------------------------------------------------------------
def test_unchanged_reference_body_blocked(engine):
    open_cycle(engine, body=REFERENCE_BODY)
    r = run(engine, "bash", CREATE)
    assert r.returncode == 2 and "reference" in r.stderr


def test_leftover_marker_blocked(engine):
    open_cycle(engine, body="Done. [SLOT: explain]\n")
    assert run(engine, "bash", CREATE).returncode == 2


def test_inline_body_blocked(engine):
    open_cycle(engine)
    assert run(engine, "bash", "gh pr create --title T --body 'hi'").returncode == 2


def test_wrong_body_file_blocked(engine):
    open_cycle(engine)
    assert run(engine, "bash", "gh pr create --title T --body-file other.md").returncode == 2


def test_empty_defense_blocked(engine):
    open_cycle(engine, defense="  ")
    r = run(engine, "bash", CREATE)
    assert r.returncode == 2 and "DEFENSE" in r.stderr


# ---- item 2: SHIP vs SHIP DRAFT ----------------------------------------------------------------
def test_ship_draft_requires_draft_flag(engine):
    open_cycle(engine, draft=True)
    assert run(engine, "bash", CREATE).returncode == 2
    assert run(engine, "bash", CREATE + " --draft").returncode == 0


def test_plain_ship_rejects_draft_flag(engine):
    open_cycle(engine, draft=False)
    assert run(engine, "bash", CREATE + " --draft").returncode == 2


@pytest.mark.parametrize("cmd", ["gh pr ready 5", "gh pr merge 5 --squash", "gh pr comment 5 -b hi",
                                 "gh pr review 5 --approve", "gh pr close 5"])
def test_human_only_actions_always_blocked(engine, cmd):
    open_cycle(engine)
    assert run(engine, "bash", cmd).returncode == 2


# ---- item 3: HOLD expiry and ABORT -------------------------------------------------------------
def test_hold_older_than_seven_days_blocked(engine):
    open_cycle(engine, age=8 * 24 * 3600)
    r = run(engine, "bash", CREATE)
    assert r.returncode == 2 and "7 days" in r.stderr


def test_hold_within_seven_days_allowed(engine):
    open_cycle(engine, age=6 * 24 * 3600)
    assert run(engine, "bash", CREATE).returncode == 0


def test_abort_cycle_locks_everything(engine):
    open_cycle(engine)
    (engine / "docs" / "LOG.md").write_text("")
    (engine / "docs" / "STATE.md").write_text("cursor: AWAITING_HUMAN\nawaiting_human: yes\n")
    hooks = engine / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy(REAL_GATE.parent / ".claude" / "hooks" / "abort_cycle.py", hooks / "abort_cycle.py")
    r = subprocess.run([sys.executable, str(hooks / "abort_cycle.py"), "too risky"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    docs = engine / "docs"
    assert not (docs / ".gate_open").exists() and not (docs / ".human_shipped").exists()
    assert (docs / "PR_BODY_DRAFT.md").read_text() == ""
    assert "cursor: IDLE" in (docs / "STATE.md").read_text()
    assert "too risky" in (docs / "LOG.md").read_text()
    assert run(engine, "bash", CREATE).returncode == 2           # locked again
    assert (engine / "repos" / "o__r" / ".git").exists()         # work is kept


def test_abort_requires_a_reason(engine):
    hooks = engine / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy(REAL_GATE.parent / ".claude" / "hooks" / "abort_cycle.py", hooks / "abort_cycle.py")
    r = subprocess.run([sys.executable, str(hooks / "abort_cycle.py")], capture_output=True, text=True)
    assert r.returncode != 0


# ---- item 4: the commit message is the human's -------------------------------------------------
def test_push_blocked_when_commit_message_is_not_the_humans(engine):
    open_cycle(engine, commit="fix: something the human wrote\n")
    r = run(engine, "push", cwd=engine / "repos" / "o__r")
    assert r.returncode == 2 and "COMMIT_MSG_DRAFT" in r.stderr


def test_push_blocked_when_commit_draft_is_still_the_reference(engine):
    open_cycle(engine, commit=REFERENCE_COMMIT)
    assert run(engine, "push", cwd=engine / "repos" / "o__r").returncode == 2


def test_push_blocked_when_commit_draft_is_empty(engine):
    open_cycle(engine, commit="\n")
    assert run(engine, "push", cwd=engine / "repos" / "o__r").returncode == 2


def test_dco_signoff_trailer_does_not_break_the_match(engine):
    open_cycle(engine)
    clone = engine / "repos" / "o__r"
    git(clone, "commit", "--amend", "-q", "-s", "-m", HUMAN_COMMIT.strip())
    assert run(engine, "push", cwd=clone).returncode == 0


def test_git_push_command_in_clone_is_gated(engine):
    clone = engine / "repos" / "o__r"
    r = run(engine, "bash", "git push fork branch", cwd=clone)
    assert r.returncode == 2
    open_cycle(engine)
    assert run(engine, "bash", "git push fork branch", cwd=clone).returncode == 0


# ---- path resolution (hook cwd differs from the engine folder; paths with spaces) ----------------
def test_body_file_resolves_from_engine_not_cwd(engine):
    open_cycle(engine)
    elsewhere = engine / "repos" / "o__r"
    assert run(engine, "bash", CREATE, cwd=elsewhere).returncode == 0


def test_relative_body_file_blocked(engine):
    """A relative path is read by gh from the shell's cwd, which the gate cannot see, so it is refused."""
    open_cycle(engine)
    cmd = "gh pr create --repo o/r --title T --body-file docs/PR_BODY_DRAFT.md"
    r = run(engine, "bash", cmd)
    assert r.returncode == 2 and "ABSOLUTE" in r.stderr


def test_inline_body_alongside_body_file_blocked(engine):
    open_cycle(engine)
    assert run(engine, "bash", CREATE + " --body 'other text'").returncode == 2
    assert run(engine, "bash", CREATE + " -b x").returncode == 2
    assert run(engine, "bash", CREATE + " --fill").returncode == 2


def test_two_body_files_blocked(engine):
    open_cycle(engine)
    assert run(engine, "bash", CREATE + " --body-file other.md").returncode == 2


def test_quoted_absolute_body_file_with_spaces_allowed(engine, tmp_path_factory):
    spaced = tmp_path_factory.mktemp("w") / "my engine"
    shutil.copytree(engine, spaced)
    open_cycle(spaced)
    assert " " in str(spaced)
    assert run(spaced, "bash", CREATE).returncode == 0


def test_quoted_other_file_with_spaces_blocked(engine):
    open_cycle(engine)
    cmd = f'gh pr create --repo o/r --title T --body-file "{engine}/docs/other file.md"'
    assert run(engine, "bash", cmd).returncode == 2


# ---- pre-open revalidation (idempotency / still-valid check) -----------------------------------
def test_create_blocked_without_revalidation(engine):
    open_cycle(engine, revalidated_age=None)
    r = run(engine, "bash", CREATE)
    assert r.returncode == 2 and "revalidate" in r.stderr


def test_create_blocked_with_stale_revalidation(engine):
    open_cycle(engine, revalidated_age=3 * 3600)
    r = run(engine, "bash", CREATE)
    assert r.returncode == 2 and "2 hours" in r.stderr


def test_api_post_create_needs_revalidation(engine):
    open_cycle(engine, revalidated_age=None)
    assert run(engine, "bash", "gh api repos/o/r/pulls -X POST -f title=T").returncode == 2


# ---- credentials never pass through model-written commands -------------------------------------
@pytest.mark.parametrize("cmd", [
    "gh auth " + "token",
    "gh auth status --show-" + "token",
    "gh auth status -" + "t",
    "gh auth " + "refresh -s workflow",
    "git cred" + "ential fill",
    "echo $GH_" + "TOKEN",
    "cat ~/.config/gh/hosts" + ".yml",
])
def test_credential_access_blocked(engine, cmd):
    r = run(engine, "bash", cmd)
    assert r.returncode == 2 and "credential" in r.stderr


def test_plain_auth_status_allowed(engine):
    assert run(engine, "bash", "gh auth status").returncode == 0
