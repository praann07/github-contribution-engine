# GitHub Contribution Engine (shareable copy)

An AI-agent workflow for making small, tested, reviewable open-source pull requests.
A safety gate (`gate.py`) stops the agent from pushing, commenting or opening PRs without a human "SHIP".

## What is in here
- `AGENTS.md` / `CLAUDE.md` - the agent's rules and workflow (identical; Claude Code reads CLAUDE.md).
- `WORKFLOW.md`, `docs/` - how a contribution cycle runs, the gates, the human checkpoint.
- `gate.py` + `.claude/settings.json` - Claude Code hook that blocks risky git/gh commands.
- `scripts/` - preflight, scout (find issues), PR checks, draft linting, audit log.
- `shared-hooks/pre-push`, `tests/test_gate.py` - git hook and tests for the gate.
- `agent-github-contribution.json` - the agent's exported settings (no keys, no memory).

## Setup
1. Install Python 3.10+, git, the GitHub CLI (`gh auth login`) and Claude Code.
2. `pip install -r requirements.txt`, then `python -m pytest tests` to confirm the gate works.
3. Search-and-replace `YOUR_GH_USER` / `YOUR_ID` in the files with your GitHub username and noreply email id.
4. Open this folder in Claude Code (or import the agent JSON in Munder Difflin) and run `python scripts/audit.py resume`.

## Rules it enforces
- Never push, comment or open a PR without the human's explicit SHIP.
- One PR open at a time; small bug fixes with a test.
- A repro test must FAIL on the unfixed code and PASS with the fix; otherwise it is discarded. Tests are a filter, not proof.
- Use your GitHub noreply email for commits (GitHub rejects private emails).

No API keys or personal memory are included. Add your own.
