# append on each valid SHIP: ## <date> <repo> PR#____ / signed_explanation / disclosure

## 2026-10-24 NVIDIA/NeMo-Agent-Toolkit PR#2443 / issue #2429
TITLE: fix(cli): don't log expanded config when --override
DEFENSE: The old code would dump the entire effective config after overrides, and environment variables would already be expanded at that point, so you could end up with API keys in your logs. Now it logs only the overridden paths. The new regression test fails without the change and succeeds with the change.
disclosure: none stated (repo has no AI-disclosure clause; human's call)
--- BODY (verbatim) ---
## About

`load_and_override_config` logs the entire effective config at INFO level once the overrides validate with `--override`. At that point `${VAR}` references have already been expanded, so API keys and other secrets from the environment end up in console output and in any logs that are captured.

This PR stops logging the expanded configuration. It only logs the overridden paths when validated. The per-override log lines from LayeredConfig.set_override remain the same.

I added a regression test in `test_config_override.py`. It sets an environment variable, loads a config file that references it, applies an override, and …and that the overridden path is. The test fails without the change, but passes with it. Ran `test_config_override.py` (9 passed) and checked the changed files with yapf and ruff. I did not run pre-commit. I did not run `ci/scripts/checks.sh`. I did not run the entire test suite.

Fixes #2429 ## By signing this PR, I confirm that:
- I have read and understand the [Contributing Guidelines](https://github.com/NVIDIA/NeMo-Agent-Toolkit/blob/develop/docs/source/resources/contributing/index.md).
- We need a "sign-off" from all committers on their commits. It confirms that the contribution is your original work, or you have the right to submit it under the same or a compatible license.
  - Any contribution with commits that are not Signed-Off will be rejected.
- When the PR is ready for review, these changes are covered by new or existing tests.
- The PR is ready for review, and the documentation is up to date with these changes.
--- COMMIT MSG (verbatim) ---
fix(cli): don't log expanded config after --override

load_and_override_config logged the full effective config after overrides were applied. At that point, environment variables will be expanded and secrets like API keys could be logged. Add regression test and only log the overridden paths.

## 2026-10-24 SylphAI-Inc/AdalFlow #232 -> PR #511 (https://github.com/SylphAI-Inc/AdalFlow/pull/511)
DEFENSE: Threads were writing to the same file with no lock, which cut lines off. I reproduced it, and the lock fixes it with a test.
TITLE: fix(utils): append_to_jsonl serialisation across threads
BODY:
## objective of this PR?

`append_to_jsonl` just calls `jsonlines.open(f, mode="a")` and writes one record per call. If multiple threads are writing to the same file (like `trainer.diagnose` run with multiple workers), their writes can interleave and a line gets chopped up by the next record. That is the corrupt line reported in #232.

This puts a module-level lock around the append so that threads in one process write one record at a time. The record is serialised (`to_dict`) outside the lock so the critical section is just the file write. Separate processes writing to the same file are still not coordinated; I noted that in the docstring.

Closes #232

## How did I verify it?

**Reproduction:** 400 records with 20k char payload each, 8 threads appending.

Before the change, 253 of 400 lines were not valid JSON. After it, all 400 are.

new test `adalflow/tests/test_file_io.py::test_append_to_jsonl_is_thread_safe` (200 records, 8 threads). Without the change it fails (`JSONDecodeError: Extra data`) and with it it passes.

`tests/test_file_io.py` and `tests/test_tracing.py`: 34 passed

`black --line-length=88` and `ruff` (versions pinned in `.pre-commit-config.yaml`) succeed on the changed files.

## Things to know

I couldn't tell if this was the exact cause of the initial report; the thread above cites a bad file from a previous run as another possibility. This fixes the thread race I was able to reproduce.

## Before Submitting

- [x] Have you discussed this issue with others? Yes, #232
- [x] I have read the Contributor Guide.
- [x] This PR does one thing.
- [x] I added a test for the change.
- [x] Existing tests I ran still pass
COMMIT MESSAGE:
fix(utils): append_to_jsonl serialisation across threads

append_to_jsonl opened the file in append mode and wrote each record without any locking. This means that threads logging to the same jsonl file (e.g. trainer.diagnose with several workers) could interleave and leave a truncated line. Add a regression test that appends from 8 threads and checks every line parses. Protect the write with a module-level lock.

## 2026-10-27 mozilla-ai/otari#2007 -> PR #2648
TITLE: fix(guardrails): warn when no file matches a glob in guardrails validate
DEFENSE: it is a warning, as a glob can legitimately name a non-existent file, such as build output, and a warning can be ignored with accept_warnings, but an error cannot
--- COMMIT MSG ---
fix(guardrails): warn when no file matches a glob in guardrails validate

The docs say validate reports a forbidden or when_changed glob that matches nothing, but it never did, so a typo in a path gate looked the same as a clean run.

Report it as warning glob-matches-no-file, checked against files
The ignore rules hold, Git tracks untracked files. It is a warning, so a gate that names a file not yet existing can accept it. shallower twin in the same list of ** glob is skipped, and the check is skipped when git cannot list the files.

Now accept the code. There are three gates in this repo's own guardrail that forbid files that should not exist.

Fixes #2007

--- PR BODY ---
## Description

`otari guardrails validate` now warns when a `forbidden` or `when_changed` glob doesn't match any file in the repo. The docs already said it reports a glob that matches nothing, but it never actually did, so a typo in a path gate looked exactly like a clean run and the gate just never fired.

The check lists the files git is tracking plus untracked files the ignore rules keep. So a file created this session counts. It is a warning, not an error, with code `glob-matches-no-file` because a glob that names a file that does not yet exist (build output, or a file a rule says must never be committed) is legitimate. A gate accepts it with `accept_warnings` added in #1998. The shallower twin of a `**` glob in the same list, e.g. `src/*.py` next to `src/**/*.py`, is not reported, as it is only there to cover the root depth. If Git cannot list the files, the check is skipped.

CI runs `validate --strict` on the guardrail of this repo itself, so three of its gates accept the code: `no-static-pwa-manifest`, `no-committed-dashboard-bundle` and `no-secret-reads`. Each prohibits a file that should not be there, so not matching anything is the desired state.

The docs had this listed under errors. I moved it to warnings, and added the code to the reference.

## How to test

1. Create `.otari/guardrails.yml` in a Git repo with a `path` gate with a `forbidden` of `["src/gone.gen.ts"]`.
2. Run `otari guardrails validate --strict`. Prints `warning[glob-matches-no-file]` for that gate and exits 1.
3. Add `accept_warnings: [glob-matches-no-file]` to the gate. It prints accepted and exits 0.
4. Create `src/gone.gen.ts` (tracked or untracked). The warning disappears.

Tests are `tests/unit/agent_gates/test_validation.py` (match, not match, no file list, empty tree, sibling globs, `**` twin, acceptance, a glob that is already an error) and `tests/unit/test_guardrails_validate_cli.py` (real `git init` repo: dead glob, tracked or new file, ignored file). Ruff passes and the validation test files pass on my machine. I haven't run them on Linux. On Windows, five tests in `test_guardrails_validate_cli.py` and 19 tests in `test_hook_cli.py` fail the same way on `main` (they need POSIX permissions and `getuid`).

## PR Type

- [ ] New Feature
- [x] Bug Fix
- [ ] Refactor
- [x] Documentation
- [ ] Infrastructure / CI

## Relevant issues

Fixes #2007

## Checklist

- [✓ ] I understand the code I am submitting.
- [x] I have added or updated tests that cover my change (`tests/unit`, `tests/integration`).
- [ ✓] I ran the Definition of Done checks locally (`make lint`, `make typecheck`, `make test`).
- [x] Documentation was updated where necessary.
- [ ] If the API contract changed, I regenerated the OpenAPI spec (`uv run python scripts/generate_openapi.py`).
- [ ] If this changes a rule in `ARCHITECTURE.md` or `scripts/check_architecture.py`, the description names the rule and says why.

## AI Usage

I USED A BIT OF AI TO KNOW WHAT EXACTLY IS HAPPENING IT IS deepseekv4 flash thats it. and Code written with Claude Code a bit and also i reveiwwed and wrote the pr

