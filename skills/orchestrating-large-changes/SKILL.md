---
name: orchestrating-large-changes
description: >
  Use when a large, multi-task change (a plan with many tasks, days of work, several
  subsystems) will be delivered by one orchestrating agent that delegates to subagents in
  parallel and integrates their branches, especially when the user will be away and wants it
  done, installed and validated for a final check. Use at the end of planning, to settle risk
  with the user and write the handoff, and at the start of the run, when an agent is told to
  follow a handoff until done. Triggers: "run this while I'm away", "unattended", "until
  Monday", "orchestrate", "delegate to subagents", "agent
  teams", "parallel lanes", "handoff", "integration branch", "live acceptance",
  "sandbox repo", "ruling", "ledger", "contract skeleton", "contracts in code", pull
  requests in several repositories, Orca workers, sub-orchestrator. Not for a single task or
  a plan small enough for one session without delegation.
license: MIT
---

# Orchestrating large changes

One agent plans, delegates, integrates, accepts live and reports a change too large for one
context. **The user decides every risk once, after the plan**; then the run is unattended
and the orchestrator rules on everything else, logging each ruling. **Contracts live in
code**: a skeleton task commits them compiling before the fan-out; prose keeps only intent.

Measured on a 33-task run: reviews paid (80% of Critical and Important findings were real
bugs). The waste: full suites in every lane under parallel load (18%+ of implementer time,
flaky timeouts; integration gates caught 0 regressions), 227 contract deltas folded by hand
into markdown beside a compiled skeleton, 160 of 556 orchestrator turns writing ledger lines.

**Done when all of these hold:**

1. Every acceptance item is proven by a command whose output is in the ledger.
2. The integration branch holds all the work, merged and green; no task stub is left.
3. Nothing the run created is left; every resource of the user is where it was; backups
   unchanged.
4. The product is in the state the handoff defines; the report is written, the user told.

## Files of a run

| File | Where | Who reads it |
|---|---|---|
| `plan/`: criteria, `core.md`, `tasks/<id>-<slug>.md`; the handoff | run directory | everyone; a task file, its delegates |
| Contract skeleton: types, fakes, conformance tests, fixtures, test stubs | the code, from T0 | delegates, through the API docs |
| `implementer.md`, `reviewer.md` | run directory | delegates |
| `ledger.md`, `reports/<id>.md`, `reviews/<id>.md`, the final report | run directory | orchestrator; fixers read their review |

The **run directory** sits outside every worktree and is never committed: specs, plans,
ledger and reports are ephemeral. The repository receives code, tests and the user-facing
docs the change itself needs, nothing else (no `docs/superpowers/`, no spec folder). Go
idioms: `references/go.md`.

## Composing with other skills

With superpowers: brainstorming and writing-plans in the format of `references/plan.md`,
saved to the run directory, never their default repository path;
subagent-driven-development with the overrides in `references/delegation.md`;
systematic-debugging; finishing-a-development-branch after the report. Several
repositories: `references/delegation-tools.md`. Without subagents: the same plan inline,
one task at a time, same ledger, reviews by a second pass.

## Workflow

1. **Plan** (`references/plan.md`): numbered criteria, a short `core.md`, a skeleton task
   T0, one short task file per task naming the packages it owns and its test stubs.
2. **Settle risk with the user, once, after the plan** (`references/risk-questions.md`).
   One message, every question with a default. Each answer becomes a rule: allowed,
   forbidden, run-owned (prefix) or reserved. Every point where the plan waits on a person
   becomes a criterion an agent checks. Prepare backup, sandbox and snapshot; write the
   handoff (`references/handoff.md`); launch the orchestrator in a fresh session.
3. **Baseline, skeleton, plan review**: a flake-free baseline under parallel load; T0; one
   reviewer attacks the plan and the skeleton against the code; apply, merge T0.
4. **Run the lanes** (`references/delegation.md`). Start a task when its files do not
   overlap a task in flight. Each lane runs the lane check, never the integration gate.
   Review every task against named concerns, adversarially where irreversible; re-review
   through the same reviewer. Merge in
   batches, one integration gate per batch, at most 2 heavy runs at once. Log with
   `scripts/ledger.py add` in the command that acts (`references/ledger.md`); end each loop
   turn with `scripts/ledger.py show`.
5. **Rule, do not ask.** What the plan, the criteria and the handoff do not settle, decide
   and log: `Ruling: <what> - <why> - cost if wrong: <what>`. Fix a wrong plan file in
   place. What the handoff reserves is not ruled on: skip the case, log a `Gap:`,
   continue. A safety mechanism of the user's tools (folder trust, prompts, credentials,
   branch protection) is always reserved: the product detects and reports it.
6. **Rehearse, then accept live** (`references/live-acceptance.md`): rehearsal on an
   intermediate head while the last tasks run, final acceptance on the final head.
7. **Final review** of the whole branch against the criteria, split by area when too large.
   One fix batch; the rest parked with rulings.
8. **Clean up, report, hand back**: verify against the snapshot; check the branch diff holds
   no plan, spec, ledger or report file; write the report in the run directory
   (`references/report.md`); tell the user its path, plus a summary in the PR body.
9. **Feedback rounds**: a rejected part of the design runs the same loop at its size. A
   user correction that reverses a ruling becomes a rule in the next handoff.

## Rationalizations

| Thought | Reality |
|---|---|
| "The migration/install/remote write is irreversible, so I'll leave it for the user" | That is a risk decision and it is theirs. Ask it in step 2 with your default. |
| "If I don't hear back I'll run the safe scope" | Silence is not an answer. The run starts after the answers. |
| "The plan doesn't answer this, ask" | Rule by the criteria, log the cost, continue. |
| "This task is mechanical, the cheap model will do" | All cheap-model tasks of a measured run failed review, +15-25 min each. Cheap tier for docs only. |
| "Describing the contract in markdown is faster" | Markdown does not compile, drifts and is folded by hand. Write the type, the fake, the fixture. |
| "I'll note this Minor for a later task" | Fix it now, drop it, or commit a skipped test in the owning package. |
| "Each lane should run the full suite to be safe" | Lanes check their packages; the batch gate covers the rest; on red, bisect the batch. |
| "Its producers are not merged, it must wait" | The contract is in the skeleton. Wait only for behavior a test needs. |
| "Write it down for the record" | The ledger, code and git are the record. |
| "Commit the plan so the next session finds it" | The run directory survives sessions. |
| "Writing the trust key makes the live test pass" | It disables the user's safety mechanism. Detect, report, log the gap. |

## Red flags

- A plan step that says "the user installs", "the user checks", "after a day of use".
- A message to the user that announces a scope instead of asking.
- A ruling without "cost if wrong".
- A delegate that touched a service, a home directory or a remote.
- A dispatch that points a delegate at the whole plan, or a review without named concerns.
- A contract, a scenario or a carried finding that exists only in prose.
- A shared file every task edits.
- A lane running the integration gate, or more than 2 heavy test runs at once.
- A report without the rollback steps.
- A plan, spec, ledger or report file in the branch diff.
