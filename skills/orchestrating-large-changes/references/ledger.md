# The ledger

One Markdown file per plan, git-ignored, in the plan's workspace directory (with
superpowers: `.superpowers/sdd/<plan>/progress.md`, created by
superpowers:subagent-driven-development; without it, any ignored path you name in the
handoff). It is the run's memory: after compaction or a crash, the next session reads it and
`git log` and resumes at the first unfinished step. Nothing in it is only in the
orchestrator's context.

## Entries

Append; never rewrite history. One line each, terse, with SHAs and agent ids.

~~~markdown
# SDD ledger — plan: <plan-path>

Handoff: <handoff-path>. Integration branch: <branch> (worktree <path>). Start head <sha>.
Baseline: <gate-command> green on <sha> (<time>).

## Steps
- P0 plan review dispatched (<model>), findings -> plan-review.md
- P0 complete: plan hardened in <sha> (<n> Critical, <n> Important, <n> Minor)
## W1 (base <sha>). Worktrees under <scratch>/wt/tNN.
- T1 dispatched (<model>, agent <id>) branch <prefix>/t01-<slug>
- T1 implemented <sha>; review dispatched (<model>)
Task 1: review 1 Needs fixes (<one line>). Fix round 1 sent.
Task 1: fix round 1/5 (<n> addressed, 0 open; commits <a>..<b>)
Task 1: complete (commits <base>..<sha>, review clean)
Task 1: minor (deferred): <one line each>
- merged T1, T2 into <sha>; gate green; their worktrees and branches removed
- W1 integration check PASS at <sha>: <each check, one clause>
## R: rehearsal on <sha>
- R/A3: <command> -> <trimmed output that proves the item>
## Final review (on <sha>) ...
## A (final acceptance) on <sha>
- A1: <command> -> <output>
- Report written: <path>. DONE.
~~~

## Rulings

Every decision the plan, the spec or the handoff did not make, by the orchestrator or
reported by a delegate:

~~~text
Ruling: <what was decided> - <why, citing the criterion or decision> - cost if wrong: <what breaks or must be redone, and who sees it>
~~~

- "Cost if wrong" is concrete: "a rebase in cli.go", "one extra column in a schema with no
  data yet", "the user sees the error without the restart command". "None" is allowed only
  when it is true (a branch name).
- A delegate's ruling is copied into the ledger with its author: `Ruling: (T7 implementer's) ...`.
- A ruling that touches a reserved item is not a ruling. Log the gap instead:
  `Gap: <what> - reserved by <rule> - <what was skipped> - <what the user must decide>`.
- Parked findings: `Final: parked - <finding> - Ruling: leave; <why> - cost: <what>`.

The report copies every ruling and gap, numbered, so the user can review them in one place.

## The ledger feeds the progress section

The ledger is the orchestrator's record; the progress state file (`progress.md`) is the
user's view of it. After each ledger entry that changes a task's or gate's state, set the
status with `progress.py set`, regenerate the report's sections and commit them. A resumed
session checks the state file against the ledger and `git log` before continuing, and
corrects the state file where they disagree.

## Resume protocol

On start, and after any compaction:

1. Read the handoff and the ledger from disk, not from memory.
2. `git log --oneline <base>..HEAD`, `git worktree list`, `git branch --list '<prefix>/*'`.
3. Where the ledger and git disagree, git wins; append a line saying what was corrected.
4. Collect results of delegates that finished while you were away (their report files and
   branches) before dispatching anything. Never re-dispatch a task with a `complete` line or
   a branch holding its commits.
5. Resume at the first step without a completion line.
