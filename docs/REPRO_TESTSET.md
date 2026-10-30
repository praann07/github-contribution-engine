# Reproduction-test benchmark (local drafter)

Run 2026-10-29. Question: how often does a local model draft a usable reproduction test? "Usable" = the test FAILS on the unfixed base and PASSES with the known fix (my gate). Harness: scratchpad `bench/bench.py` (kept outside the repo). Read-only on GitHub; all work in temp trees under `C:/bt`.

## 1. Test set (10 real, already-fixed issues)

Each case was first checked with an **oracle**: the fix's own new tests must fail on the base and pass on the fix. A case that fails the oracle cannot judge a model, so it is excluded (and listed, not hidden).

| # | Case | Repo | Base -> fix | Oracle | Status |
|---|---|---|---|---|---|
| 1 | [otari #2626](https://github.com/mozilla-ai/otari/pull/2626) access log line ending in `api_token` not masked | mozilla-ai/otari | d45913be -> cd73677c | pass | **run** |
| 2 | [otari #2621](https://github.com/mozilla-ai/otari/pull/2621) empty `OTARI_SECRET_KEY` message | mozilla-ai/otari | 8280637b -> 149cb517 | pass | **run** |
| 3 | [otari #2622](https://github.com/mozilla-ai/otari/pull/2622) warn on unknown config keys | mozilla-ai/otari | 33cdc771 -> 481678b8 | pass | **run** |
| 4 | [DocsGPT #3062](https://github.com/arc53/DocsGPT/pull/3062) read md/rst/csv as UTF-8 (mine) | arc53/DocsGPT | bfbed2b^ -> eaf6d8b | pass | **run** |
| 5 | [AdalFlow #232](https://github.com/SylphAI-Inc/AdalFlow/issues/232) corrupted jsonl across threads (my PR #511) | SylphAI-Inc/AdalFlow | 08fe211^ -> 08fe211 | pass | **run** |
| 6 | [PyRIT #3154](https://github.com/microsoft/PyRIT/pull/3154) request timeout on dataset downloads (mine, merged) | microsoft/PyRIT | 4da9c11^ -> 4da9c11 | pass | **run** |
| 7 | [NeMo #2429](https://github.com/NVIDIA/NeMo-Agent-Toolkit/issues/2429) `--override` logs secrets (my PR #2443, merged) | NVIDIA/NeMo-Agent-Toolkit | 9ff2321 -> a42ff95 | pass | **run** |
| 8 | [otari #2007](https://github.com/mozilla-ai/otari/issues/2007) glob matches no file (my PR #2648) | mozilla-ai/otari | cf7d6b72^ -> cf7d6b72 | **fails**: test setup errors even with the fix (102 errors in DB fixtures) | excluded |
| 9 | [otari #2608](https://github.com/mozilla-ai/otari/pull/2608) mask `key-` tokens | mozilla-ai/otari | f1b9ad30^ -> f1b9ad30 | **fails**: the fix's own tests fail on Windows with the fix applied | excluded |
| 10 | [otari #2620](https://github.com/mozilla-ai/otari/pull/2620) reserved names for hosted providers | mozilla-ai/otari | 8280637b^ -> 8280637b | **fails**: integration conftest errors on both sides | excluded |

Only 7 of the 10 could be used. The ask was 8-12 usable cases; I did not pad the set with cases that cannot be judged.

## 2. Setup

- Model: `qwen2.5-coder:7b` via Ollama, `num_ctx` 8192, `num_predict` 2000, temperature 0.2.
- Prompt: issue/PR text (first 1400 chars), up to 3 snippets of the unfixed code around the changed lines, and the start of the repo's existing test file (for its imports, helpers and style). The fix itself is never shown.
- 2 attempts per case. Attempt 2 gets attempt 1's code plus the pytest output.
- Gate: run the draft on the base tree (`git archive`) and on the fixed tree; need base = FAIL, fix = PASS.
- Not run: MiniCPM5-2B, `qwen3.5:9b`, `nemotron-3.5-bolt:e4b`, and Grok. Memory was critically low (2 GB free) and the downloads were stopped by the system, so I did not start them. They are not counted as failures.
- Harness limit: for DocsGPT, AdalFlow, PyRIT and NeMo the drafts ran with `--noconftest` (their root conftests need services that are not installed), so a draft that relies on a repo fixture could not work there. otari ran with its real conftest.

## 3. Results: qwen2.5-coder:7b

| Issue | Model | Attempt | Fails on base? | Passes with fix? | Reason |
|---|---|---|---|---|---|
| otari #2626 | qwen7b | 1 | yes | no | assertion wrong: the test also fails on fixed code (wrong expectation about the log format) |
| otari #2626 | qwen7b | 2 | yes | no | same, a second invented test also fails on fixed code |
| otari #2621 | qwen7b | 1 | yes | no | fails with the fix too (wrong expectation about the error text) |
| otari #2621 | qwen7b | 2 | yes | error | the fixed code raises an error in the draft's setup |
| otari #2622 | qwen7b | 1 | yes | no | log-capture assertions fail on fixed code |
| otari #2622 | qwen7b | 2 | yes | no | same, plus a "Failed:" from the wrong exception expectation |
| DocsGPT #3062 | qwen7b | 1 | yes | no | right bug (UnicodeDecodeError on base) but the expected string in the assert is wrong, so it fails with the fix |
| DocsGPT #3062 | qwen7b | 2 | yes | no | same wrong expected string |
| AdalFlow #232 | qwen7b | 1 | error | error | invented helper `save_jsonl` (import error) |
| AdalFlow #232 | qwen7b | 2 | error | error | same invented helper |
| PyRIT #3154 | qwen7b | 1 | error | error | `NameError: SeedDataset` (name never imported) |
| PyRIT #3154 | qwen7b | 2 | error | error | same |
| NeMo #2429 | qwen7b | 1 | yes | no | secret-leak assertion fails on fixed code too |
| NeMo #2429 | qwen7b | 2 | yes | no | same |

## 4. Summary

1. Pass rate: qwen2.5-coder:7b 0 of 7 cases (0 of 14 attempts). MiniCPM 2B, qwen3.5:9b, nemotron and Grok: not run yet.
2. Most common failure: the draft reproduces the symptom but asserts the wrong value, so it also fails on the fixed code (5 of 7 cases). Second: an invented helper or name (`save_jsonl`, `SeedDataset`), 2 of 7.
3. The second attempt with the failure output fed back did not rescue any case; it repeated the same mistake.
4. The gate did its job: every bad draft was caught automatically, none could have reached a PR. Several drafts failed on base for the right reason (e.g. the UTF-8 decode error), so the model understands the issue but not the exact expected behaviour.
5. Verdict: do not rely on the 7B to write the test. Keep it, if at all, as a cheap first draft that a stronger model or I rewrite. Next test: a hosted tester (Grok) and the two newer local models on this same set, since 7 cases and one model is a small sample.
