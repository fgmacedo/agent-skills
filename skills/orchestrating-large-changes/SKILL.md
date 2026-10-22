---
name: orchestrating-large-changes
description: >
  Use when a large, multi-task change (a plan with many tasks, days of work, several
  subsystems) will be delivered by one orchestrating agent that delegates to subagents in
  parallel and integrates their branches, especially when the user will be away and wants it
  done, installed and validated for a final check. Use at the end of planning, to settle risk
  with the user and write the handoff, and at the start of the run, when an agent is told to
  follow a handoff until done. Triggers: "run this while I'm away", "unattended", "until
  Monday", "orchestrate", "orchestrator and integrator", "delegate to subagents", "agent
  teams", "parallel lanes", "waves", "handoff", "integration branch", "live acceptance",
  "sandbox repo", "ruling", "ledger", "spec deltas", "OpenSpec", pull requests in several
  repositories, Orca workers, sub-orchestrator. Not for a single task or a plan small enough
  for one session without delegation.
license: MIT
---

# Orchestrating large changes

One agent plans, delegates, integrates, accepts live and reports a change too large for one
context. Two things are settled before the run: **the user decides every risk once, after
the plan, and the answers become written rules**; then the run is unattended and the
orchestrator rules on everything else, logging each ruling.

Where the time goes, measured on a 23-task run: review rounds (no task passed its first
review; each round cost 10-25 min), context re-read by every delegate (150-500 K tokens
each), a full gate run after every merge, and cheap-model tasks that failed and were redone.
The format below cuts each one: a delegate reads only the core and its own task file; the
implementer attacks the review focus before reporting; the full gate runs once per merge
batch on the integration branch (each implementer runs it once, rebased, before
reporting); every task that changes code runs on the most capable model.

**Done when all of these hold:**

1. Every acceptance item is proven by a command whose output is in the ledger.
2. The integration branch holds all the work, merged and green.
3. Nothing the run created is left (delegate worktrees, branches, run-prefixed resources);
   every resource of the user is where it was; backups unchanged.
4. The product is in the state the handoff defines.
5. The report is written and the user is told where it is.

## Files of a run

| File | Where | Who reads it |
|---|---|---|
| `core.md`: goal, constraints, review focus, graph | plan directory, committed | everyone |
| `tasks/<id>-<slug>.md`: one task's files, contracts, scenarios | plan directory, committed | its implementer and reviewer |
| `contracts.md`: interfaces as they are now | plan directory, committed, folded at each merge | delegates, the sections their task names |
| `implementer.md`, `reviewer.md` | run directory | delegates |
| `ledger.md`, `reports/<id>.md`, `reviews/<id>.md` | run directory | orchestrator; fixers read their review |

The **run directory** sits outside every worktree (for example a sibling
`<workspaces>/<repo>/.<run>-run/`): repository-wide scans and archtests read ignored files
too. Delegates read the plan files by absolute path from the integration worktree, so they
always see the current contracts.

## Composing with other skills

| Need | With superpowers | Without |
|---|---|---|
| Spec and plan | brainstorming, writing-plans, written in the format of `references/plan.md` | `references/plan.md` |
| Per-task loop | subagent-driven-development, with the overrides in `references/delegation.md` | `references/delegation.md` |
| Diagnosing a failure | systematic-debugging | One variable at a time, cause before fix |
| Ending | finishing-a-development-branch, after the report | Report, then ask how to integrate |

Several repositories: `references/delegation-tools.md`. Without subagents: run the same
plan inline, one task at a time, same ledger, reviews by a second pass.

## Workflow

1. **Plan in two levels** (`references/plan.md`): numbered criteria, `core.md`, one task
   file per task with requirements as WHEN/THEN scenarios that name their tests, the files
   it touches and the real overlap with other tasks, contracts written in full.
2. **Settle risk with the user, once, after the plan** (`references/risk-questions.md`).
   One message, every question with a proposed default; never "if I don't hear back". Each
   answer becomes a rule: allowed (exact names), forbidden, run-owned (prefix) or reserved.
   Replace every point where the plan waits on a person with a criterion an agent checks.
   Prepare the backup, the sandbox and the snapshot. Write the handoff
   (`references/handoff.md`) and launch the orchestrator in a fresh session.
3. **Harden the plan**: one reviewer on the most capable model attacks it against the code
   (prompt in `references/plan.md`). Apply what holds up, commit.
4. **Run the lanes** (`references/delegation.md`). Start a task as soon as its contracts are
   written and its files do not overlap a task in flight. Review every task against named
   concerns; re-review through the same reviewer. Merge in batches, fold each task's
   contract deltas into `contracts.md`, run the full gate once per batch. Log every state
   change as one ledger line (`references/ledger.md`) and end each loop turn with the board
   from `scripts/ledger.py show`.
5. **Rule, do not ask.** What the plan, the criteria and the handoff do not settle, decide
   and log: `Ruling: <what> - <why> - cost if wrong: <what>`. Fix the plan when it is wrong,
   in the same commit as the fix. What the handoff reserves is not ruled on: skip the case,
   log a `Gap:`, continue. A safety mechanism of the user's tools (folder trust, permission
   prompts, credentials, branch protection) is always reserved: make the product detect and
   report it; never write the setting that disables it.
6. **Rehearse, then accept live** (`references/live-acceptance.md`): rehearsal on an
   intermediate head while the last tasks run, final acceptance on the final head.
7. **Final review** of the whole branch on the most capable model against the criteria and
   `contracts.md`, split by architectural area when too large (a ruling). One fix batch for
   what must be fixed; the rest parked with rulings.
8. **Clean up, report, hand back**: verify against the snapshot, write the report
   (`references/report.md`), tell the user where it is.
9. **Feedback rounds**: a rejected part of the design runs the same loop at its size. A
   user correction that reverses a ruling becomes a rule in the next handoff.

## Rationalizations

| Thought | Reality |
|---|---|
| "The migration/install/remote write is irreversible, so I'll leave it for the user" | That is a risk decision and it is theirs. Ask it in step 2 with your default. |
| "If I don't hear back I'll run the safe scope" | Silence is not an answer. The run starts after the answers. |
| "A gate failed twice, stop the run" | Diagnose and loop. Stop only a reserved case. |
| "The plan doesn't answer this, ask" | Rule by the criteria, log the cost, continue. |
| "This task is mechanical, the cheap model will do" | All three cheap-model tasks of the measured run failed review and were redone on the capable one, +15-25 min each. Cheap tier for docs only. |
| "The delegate needs the whole plan for context" | It needs the core, its task file and the contract sections it names. The rest is noise it pays for every round. |
| "Its producers are not merged, it must wait" | It waits only for written contracts and disjoint files. Starting by overlap cut an hour from the measured critical path. |
| "Run the full gate after each merge to know which one broke it" | Once per batch; on red, bisect the batch's merge commits. |
| "Write it down for the record" | The ledger line and git are the record. Nothing else. |
| "Writing the trust key makes the live test pass" | It disables the user's safety mechanism. Detect, report, log the gap. |
| "I remember which tasks are merged" | After compaction, the ledger and `git log` are the truth. |

## Red flags

- A plan step that says "the user installs", "the user checks", "after a day of use".
- A message to the user that announces a scope instead of asking.
- A ruling without "cost if wrong".
- A delegate that touched a service, a home directory or a remote.
- A dispatch that points a delegate at the whole plan, or a review without named concerns.
- A requirement without a scenario, or a scenario without a test name.
- A report without the rollback steps.
