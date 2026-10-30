# CONTRIBUTION ENGINE: WORKFLOW DIAGRAM

Picture of what WORKFLOW.md, CLAUDE.md and docs/PR_CHECKPOINTS.md already say.
If this file and WORKFLOW.md disagree, WORKFLOW.md wins.
Orbit: mechanistic interpretability / inference efficiency.
Legend:  [AGENT] = the AI does it   [HUMAN] = only the human can do it   [GATE] = enforced by code

Core idea: the AI finds, fixes and tests. The HUMAN writes and ships everything a maintainer reads.

---------------------------------------------------------------------------------------------

## 1. THE BIG PICTURE (one cycle)

        +------------------------------------+
        |  START OF EVERY TURN   [AGENT]     |
        |  read docs/STATE.md -> cursor      |
        |  print [READ] and [OBEY] header    |
        +----------------+-------------------+
                         |
                         v
        +------------------------------------+
        |  STAGE 1  SCOPE        [AGENT]     |----- no valid need -----+
        |  pick ONE real, verified need      |                         |
        +----------------+-------------------+                         |
                         | need found                                  |
                         v                                             |
        +------------------------------------+                         |
        |  STAGE 2  DRAFT        [AGENT]     |                         |
        |  smallest correct fix + tests      |                         |
        +----------------+-------------------+                         |
                         v                                             |
        +------------------------------------+                         |
        |  STAGE 3  LOCAL_GATE   [AGENT]     |<--- any red: fix --+    |
        |  repo's own checks, all green      |---------------------+   |
        +----------------+-------------------+                         |
                         | all green                                   |
                         v                                             |
        +====================================+                         |
        ||  STAGE 4  HUMAN_GATE   [HUMAN]   ||  AI hands over facts +   |
        ||  human rewrites the PR text      ||  reference draft, STOPS  |
        ||  human types SHIP + DEFENSE=     ||                         |
        +================+===================+                         |
                         | SHIP                                        |
                         v                                             |
        +------------------------------------+                         |
        |  STAGE 5  OPEN         [AGENT]     |                         |
        |  gh pr create, human's file as-is  |                         |
        |  then read back the PR's true state|                         |
        +----------------+-------------------+                         |
                         v                                             |
        +------------------------------------+                         |
        |  STAGE 6  RECORD       [AGENT]     |                         |
        |  update STATE / LOG / GATES, lock  |                         |
        +----------------+-------------------+                         |
                         v                                             v
                    +----------+                          +-----------------------+
                    |   IDLE   |<-------------------------|  NO_VALID_TARGET      |
                    +----------+     honest zero-PR       |  log reason, end cycle|
                                     cycle = SUCCESS      +-----------------------+

---------------------------------------------------------------------------------------------

## 2. STAGE 1 IN DETAIL: "is there real work here?"

   allowlist repo (docs/TARGETS.md only; not listed = no PR)
        |
        v
   +---------------------------------------------+
   | resolve canonical name:                     |
   |   gh repo view <owner>/<repo> --json ...    |
   +--------------------+------------------------+
                        v
   +---------------------------------------------+  ALL 3 true (AND)   +-----------------+
   | FARM CHECK (gh only, NO clone)              |------------------->| FARMED: skip,   |
   |  a) REPO has 0 good-first-issue AND 0       |                    | log, next repo  |
   |     help-wanted issues (maintainers curate  |                    +-----------------+
   |     no starter work)                        |
   |  b) existing PRs have only [bot]/App reviews|
   |  c) in-orbit bugs are already claimed by    |
   |     the reporters' own same-day PRs         |
   |  One or two true = still usable, note it.   |
   +--------------------+------------------------+
                        | passes
                        v
   +---------------------------------------------+  no CPU, key-free test   +--------------+
   | ENV CHECK (tiered, pre-clone)               |-- subset can prove it -->| INFEASIBLE:  |
   |  FULL      = default test env runs here     |  needs: nvcc / Docker /  | skip, log    |
   |  TARGETED  = named CPU test subset only     |  C++ build, another OS,  +--------------+
   |  (read CI workflows for hidden secrets)     |  GPU / special hardware,
   +--------------------+------------------------+  or paid API keys
                        | passes
                        v
   +---------------------------------------------+   forbids AI / unsolicited   +--------+
   | READ CONTRIBUTING, CODE_OF_CONDUCT,         |----------------------------->| EXCLUDE|
   | SECURITY, AI policy                         |                              | log    |
   +--------------------+------------------------+                              +--------+
                        | allowed
                        v
   +---------------------------------------------+   maintainer said "not now"   +--------+
   | VERIFY THE NEED IS REAL (PR_CHECKPOINTS)    |   or only a bot engaged  ---->| next   |
   |  read linked issue + existing reviews       |                               | repo   |
   |  reproduce the bug / failing test           |                               +--------+
   +--------------------+------------------------+
                        | real, unclaimed, verifiable on this laptop
                        v
                  go to STAGE 2

   Never: invent work, typo/style drive-bys, claim an issue someone else is already fixing.

---------------------------------------------------------------------------------------------

## 3. STAGE 3 IN DETAIL: local checks (CI-green is the floor, not the bar)

   pre-commit --> ruff --> mypy / pyright --> pytest --> act (CI dry run) --> gitleaks
       |            |            |              |             |                 |
       +------------+------------+--------------+-------------+-----------------+
                    any red  ==>  fix it, re-run stage 3 (cursor = FAILED_LOCAL_GATE)
       If the full suite is too heavy, run a NAMED subset and RECORD which one: in the
       docs/HUMAN_GATE.md facts (next to the pasted test output) + one line in docs/LOG.md.

---------------------------------------------------------------------------------------------

## 4. STAGE 4 IN DETAIL: the authorship hand-off (the part that protects acceptance)

   [AGENT] fills docs/HUMAN_GATE.md   : diff stat, REAL pasted test output, issue #, 1-line reason,
        |                               the repo's AI-disclosure policy
        v
   [AGENT] writes docs/PR_BODY_DRAFT.md    = REFERENCE (facts + [SLOT:] markers)
   [AGENT] writes docs/COMMIT_MSG_DRAFT.md = REFERENCE (repo's commit style, DCO if required)
        |                               top line "REFERENCE -- REWRITE IN YOUR OWN WORDS"
        v
   [AGENT] runs  python .claude/hooks/open_gate.py
        |        -> stores BOTH reference hashes + a timestamp in docs/.gate_open
        v
   cursor = AWAITING_HUMAN        AI STOPS. Opens nothing.
        |
        v
   +============================================================================+
   | [HUMAN] rewrites BOTH files in their own words, then sends ONE of:         |
   |   SHIP / SHIP DRAFT     + a line  DEFENSE=<why this change is right>       |
   |   ABORT <reason>   -> abort_cycle.py: gate locked, drafts emptied, logged, |
   |                       cursor IDLE, local branch kept, GitHub untouched     |
   |   HOLD             -> keep everything; gate expires after 7 days           |
   +=====+==========================+===============================+===========+
         | SHIP / SHIP DRAFT        | ABORT                         | HOLD
         v                          v                               v
   (gate below)                  IDLE                  stay AWAITING_HUMAN (max 7 days)

   Gate input from SHIP:
   +----------------------------------------------------------------------------+
   | [GATE] gate.py + global pre-push hook + harness permission. ALL must hold:  |
   |   - docs/.human_shipped exists  (written only after a real SHIP + DEFENSE)  |
   |   - docs/.gate_open exists                                                  |
   |   - PR_BODY_DRAFT.md changed from the recorded reference hash               |
   |   - no leftover [SLOT:] or "REFERENCE -- REWRITE" marker                    |
   |   - command uses  --body-file docs/PR_BODY_DRAFT.md                         |
   |   - --draft present if and only if the human typed SHIP DRAFT               |
   |   - gate is younger than 7 days                                             |
   |   For git push inside repos/ ALSO:                                          |
   |   - COMMIT_MSG_DRAFT.md rewritten (same checks) and equal to HEAD's message |
   |   Always blocked for the AI: gh pr ready / merge / comment / review / close |
   +--------------+--------------------------------+-----------------------------+
          all pass |                                | any fails
                   v                                v
          STAGE 5: gh pr create          BLOCKED. Nothing is pushed or opened.
          (--draft only for SHIP DRAFT;
           human clicks "Ready for review")

---------------------------------------------------------------------------------------------

## 5. STAGE 5-6 IN DETAIL: after the PR is open (read the real state, never nag)

   gh pr view <N> --json state,reviewDecision,mergeStateStatus,statusCheckRollup,reviews,...
                          |
         trust ONLY aggregate fields, NOT role badges
                          v
   +--------------------------------------------------------------------------------+
   | reviewDecision        mergeStateStatus       what it means        agent action |
   |--------------------------------------------------------------------------------|
   | REVIEW_REQUIRED       BLOCKED                nobody counting yet   wait         |
   | CHANGES_REQUESTED     (human reviewer)       edits wanted          surface to   |
   |                                                                    the HUMAN    |
   | APPROVED              CLEAN                  ready                 human merges |
   | any                   CLA / checks QUEUED    first-time gate       BLOCKED_     |
   |                       / BEHIND / CONFLICTING                       MAINTAINER   |
   +--------------------------------------------------------------------------------+

   Comment from a [bot] / App?   ->  IGNORE. No re-push, no reply, not a sign-off.
   Comment from a human that counts? -> show it to the HUMAN; never auto-fix-and-push.

   BLOCKED_MAINTAINER means: write the exact blocker to STATE.md + LOG.md, then STOP.
       No re-pushes to "speed it up".  No @-mentions.  No duplicate PRs.  No agent comments.

   Stage 6 RECORD: update board row, append LOG.md, append shipped text to GATES.md,
       rm docs/.gate_open docs/.human_shipped   (next cycle starts locked), cursor -> IDLE.

---------------------------------------------------------------------------------------------

## 6. CURSOR STATE MACHINE (legal moves only; anything else is refused and logged)

   IDLE --> SCOPED --> DRAFTED --> LOCAL_GATE_PASSED --> AWAITING_HUMAN --> OPENED --> RECORDED --> IDLE
     ^         |                          ^   |            |   ^    |                 |
     |         v                          |   v            |   |    |                 v
     +---- NO_VALID_TARGET        FAILED_LOCAL_GATE        |   +HOLD+          BLOCKED_MAINTAINER
     ^                            (fix, then re-run 3)     v   (max 7 days)    (stop touching that PR)
     +------------------------------------------------ ABORTED   (human types ABORT <reason>)

   ILLEGAL:  SCOPED -> OPENED        LOCAL_GATE_PASSED -> OPENED
             AWAITING_HUMAN -> OPENED without .human_shipped or with an unchanged / marker-laden body
             a push whose HEAD commit message is not the human's COMMIT_MSG_DRAFT.md
             any PR or push through MCP / web tools (they bypass the gate)
             the agent writing the FINAL PR title, body, final commit or comment
             the agent running gh pr ready / merge / comment / review / close

---------------------------------------------------------------------------------------------

## 7. WHAT MAKES A PR GET ACCEPTED (lessons from the two real PRs we shipped)

   +-----------------------------+-------------------------------------------------------------+
   | Habit                       | Evidence                                                    |
   |-----------------------------+-------------------------------------------------------------|
   | one real bug, smallest fix  | PyRIT #3154: 2 call sites + 2 tests, merged Oct 13           |
   | issue opened first          | PyRIT asked for it; #3153 -> PR #3154                        |
   | tests fail without the fix  | both PRs showed red before / green after                     |
   | repo rules followed exactly | CLA signed; DocsGPT type hints + docstrings added on request |
   | no bot-chasing              | Vercel failures ignored; only human-counting reviews matter  |
   | patience                    | PyRIT approved in about a day; DocsGPT still waiting         |
   +-----------------------------+-------------------------------------------------------------+

---------------------------------------------------------------------------------------------

## 8. HONEST LIMITS (read this before trusting the diagram)

   1. No pipeline can make EVERY contribution accepted. Maintainers decide, and they reject or
      ignore good work for reasons outside our control (scope, timing, burnout, project direction).
      The achievable goal is a HIGH acceptance rate by sending only verified, wanted, small PRs.
      An honest zero-PR cycle is a success, not a failure.
   2. The gate stops the AI from posting text under the human's name. It does not decide whether
      the human's rewrite is good. Quality of the human's words and DEFENSE line matters most.
   3. Some repos ban or discourage AI-assisted PRs (example: peft demands "authored by a human").
      Those are excluded. Follow each repo's AI-disclosure rule; the human states it, never the AI.
   4. PRs open live by default. SHIP DRAFT is available when you want a zero-pressure look at the
      rendered PR first; the human then clicks "Ready for review" in GitHub. Drafts are often not
      reviewed by maintainers, so use the option when it helps, not as a blanket rule.
   5. Gate coverage: the git pre-push hook covers pushes inside repos/ only. The Claude Code hook
      (.claude/settings.json) covers shell commands run from this folder. A different tool or a
      terminal outside this folder is NOT covered, so run PR commands only from here.
   6. Known gap: the two PRs shipped earlier in this session (#3062, #3154) were drafted by the AI
      and shipped before this gate existed. They do not follow the stage-4 rule. Every future PR
      must go through stage 4.
