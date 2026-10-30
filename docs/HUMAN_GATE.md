# HUMAN GATE FACTS — 2026-10-25 — mozilla-ai/otari issue #2007
(Agent-filled facts only. Everything maintainer-facing is yours to write.)

## What this is
- Issue #2007 (filed by maintainer peteski22, bug, area/cli, 0 comments, no PR, no assignee): `otari guardrails validate` does not report a `forbidden` / `when_changed` glob that matches no file, although the docs say it does.
- Fix is committed LOCALLY only: `repos/mozilla-ai__otari`, branch `feat/validate-glob-matches-no-file`, commit 72f7d34 (base main 910de2b). Nothing forked, pushed, commented or opened.

## Design decisions you must be able to explain
- Warning with code `glob-matches-no-file`, NOT an error. The docs said error. Reason: a glob naming a future build output or a file that must never exist is legitimate, and only a warning can be accepted via `accept_warnings` (#1998). The docs line was moved from errors to warnings. The issue itself says accept_warnings "would cover it if this is a warning". If the maintainer wants an error, it is a small change.
- File list = `git ls-files --cached --others --exclude-standard -z` (tracked + untracked-not-ignored). If git fails, the check is skipped (None), not guessed.
- The shallower twin of a `**` glob in the same list is skipped (e.g. `src/*.py` beside `src/**/*.py`), because this repo's own gates add twins on purpose and `src/` holds no .py at that depth.
- `validate_policy` stays pure: it takes a new optional `repo_files` argument, like `probe_verifier`.

## Side effect to know about (the repo's CI runs `validate --repo-only --strict`)
- After the change the repo's own guardrail warned on 3 gates, all "forbid a file that should not exist": `no-static-pwa-manifest`, `no-committed-dashboard-bundle` (.otari/guardrails/generated-artifacts.yml) and `no-secret-reads` (.otari/guardrails/secrets.yml). I added `accept_warnings: [glob-matches-no-file]` to those three. After that, `otari guardrails validate --repo-only --strict` exits 0 locally. Say this in the PR so the maintainer is not surprised.

## Files changed (9, +~160 -5)
- cli/src/otari_agent/domain/types.py (new WarningCode), domain/validation.py (check + `repo_files` arg), hook.py (`_hook_repo_files`, pass it in, docstring)
- docs/agent-guardrails.md, docs/agent-guardrails-reference.md
- tests/unit/agent_gates/test_validation.py (+8 tests, helper takes repo_files), tests/unit/test_guardrails_validate_cli.py (+3 tests with a real `git init`)
- .otari/guardrails/generated-artifacts.yml, .otari/guardrails/secrets.yml

## Tests actually observed (Windows, Python 3.13, venv outside the repo)
- agent_gates + validate CLI: 454 passed, 5 failed. The same 5 fail on base `main` (stash test): POSIX-only (permission bits, getuid). 24 failures in the wider hook/CLI set are identical before and after.
- ruff check + ruff format --check clean. mypy `cli/src`: 7 errors, identical on base (POSIX-only modules: getuid, killpg, flock).
- NOT run: `make lint` (pre-commit, needs Linux/web tools), `make test` full suite, anything on Linux, the gateway/integration tests.

## Things the maintainers' rules ask of you (otari AGENTS.md / template)
- An agent never files an issue; the issue exists already, so no new issue.
- The PR template has a checklist; "I understand the code" and "ran make lint / typecheck / test" are YOURS to tick only if true. I did not run `make lint` or `make test`.
- AI Usage section is yours and must be honest.
- Do not hand-edit CHANGELOG.md. No em dashes or `--` in prose. Conventional title (the commit title works).
- Squash-merge repo; many external PRs sit unreviewed here (hasangzl, agpituk, aittalam have merged), so expect a wait.

## Suggested order (you do these; I never post)
1. Read the diff: `git -C repos/mozilla-ai__otari show 72f7d34`. Run the new tests yourself if you can. You must be able to explain every line.
2. Post a short claim comment on #2007 in your own words (draft below, reference only).
3. Rewrite docs/PR_BODY_DRAFT.md and docs/COMMIT_MSG_DRAFT.md in your own words (delete the REFERENCE line).
4. Reply SHIP with a `DEFENSE=` line (one sentence in your words: why warning not error, and why the twin is skipped). I refuse SHIP without DEFENSE.

## Claim comment (reference only, rewrite)
I'd like to take this. My plan is to report it as a warning with its own code, so a glob that names a file that doesn't exist yet can be accepted with accept_warnings, and to check against the files Git tracks plus untracked ones that aren't ignored. Say if you'd rather it were an error.

## Honest limits
- The fork `YOUR_GH_USER/otari` does not exist yet; opening the PR creates it (needs your SHIP).
- One open question I could not settle without the maintainers: error vs warning. I chose warning for the reason above.
