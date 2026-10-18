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
  "sandbox repo", "ruling", "ledger", pull requests in several repositories, Orca workers,
  sub-orchestrator. Not for a single task or a plan small enough for one session without
  delegation.
license: MIT
---

# Orchestrating large changes

One agent plans, delegates, integrates, accepts live and reports a change too large for one
context. It works because two things are settled before the run: **the user decides every
risk once, after the plan, and the answers become written rules**; then the run is
unattended, and the orchestrator rules on everything else itself, logging each ruling.

**Done when all of these hold:**

1. Every acceptance item is proven by a command whose output is in the ledger.
2. The integration branch holds all the work, merged and green.
3. Nothing the run created is left: no delegate worktree or branch, no run-prefixed
   resource; every resource of the user is where it was; backups unchanged.
4. The product is in the state the handoff defines (installed, automation paused or not).
5. The report is written and the user is told where it is.

## Composing with other skills

| Need | With superpowers | Without |
|---|---|---|
| Spec and plan | brainstorming, writing-plans, plus the lane section of `references/plan-lanes.md` | Same content by hand: per task exact files, interfaces, tests, acceptance |
| Per-task loop: implementer, review, fix rounds, ledger | subagent-driven-development (this skill overrides only its one-implementer-at-a-time rule, by ruling) | `references/delegation.md` and `references/ledger.md` are the whole loop |
| Worktrees | using-git-worktrees for the integration worktree | `git worktree add` as in `references/delegation.md` |
| Reviews | requesting-code-review for prompts | Reviewer contract in `references/delegation.md` |
| Diagnosing a failure | systematic-debugging | Reproduce narrowly, one variable at a time, cause before fix |
| Ending | finishing-a-development-branch, after the report | Report, then ask how to integrate |

Without subagents at all, run the same plan inline (one task at a time, same ledger, same
reviews by a second pass) and skip the parallel parts.

## Choosing the delegation tool

| The result is | Delegate with |
|---|---|
| Pull requests in one repository | Plain subagents, one per task, each in its own worktree; an agent team member only when a delegate needs several turns with its context kept |
| Pull requests in more than one repository, Orca present | One sub-orchestrator per repository as an Orca supervised worker, which runs this same skill on its slice and negotiates contract changes with you through Orca messages |
| Pull requests in more than one repository, no Orca | Plain subagents in worktrees of each repository; you own every PR |

Details, the child's handoff and the negotiation rules: `references/delegation-tools.md`.

## Workflow

### 1. Plan for lanes

Write success criteria an agent can check, then the plan, then its execution shape: a
dependency graph, waves, a lane table where each task owns its files, contracts written in
full so consumers code against them before producers merge, and an integration check per
wave. `references/plan-lanes.md`. Order by value to the user; phase boundaries only where an
irreversible consequence must be verified, and an agent runs that check.

### 2. Settle risk with the user: once, after the plan

The risk decisions are the user's. Not yours to take in either direction: do not assume
permission for an irreversible step, and do not quietly cut it from the scope either.

1. Go through `references/risk-questions.md` against the plan. Every task that touches
   anything outside the repository produces a question.
2. Send **one** message with every question and your proposed default for each. Ask; never
   "if I don't hear back, I'll go with X".
3. Turn each answer into a rule: allowed (with exact names), forbidden, run-owned (with a
   prefix), or reserved (the run skips the case and reports it).
4. Replace every point where the plan waits on a person with a criterion an agent can
   evaluate and the permission to act on it.
5. Prepare what the answers allow and the run would hesitate to do: backup with checksums,
   sandbox with scripted actors, a snapshot of the user's resources.
6. Write the handoff (`references/handoff.md`), commit it with the plan, and launch the
   orchestrator in a fresh session with the handoff as its prompt.

### 3. Harden the plan

First act of the run: one reviewer on the most capable model attacks the plan against the
code (prompt in `references/plan-lanes.md`). Apply what holds up, commit, then delegate.

### 4. Run the waves

- Start the ledger (`references/ledger.md`) with the plan, handoff, branch and baseline gate.
- Across repositories with Orca: start one sub-orchestrator per repository with its own
  handoff, answer its questions from your criteria as they arrive, and run the joint
  acceptance when all have settled (`references/delegation-tools.md`). The steps below are
  then what each child does in its repository.
- Per wave: one implementer per task in its own worktree and branch, dispatched with five
  lines that point at shared files (`references/delegation.md`). Tasks whose inputs are all
  merged start early.
- Each task: review, fix rounds, scoped re-review, as superpowers:subagent-driven-development
  (or `references/delegation.md`) says.
- Merge in task order with `--no-ff`, run the wave's integration check, remove the wave's
  worktrees and branches, log it. Release the next wave only on green.
- Keep your context small: delegates reply with a short status; reports, diffs and findings
  live in files you read only when a verdict is not clean.

### 5. Rule, do not ask

Anything the plan, the spec and the handoff do not settle, you decide by the success
criteria, and log: `Ruling: <what> - <why> - cost if wrong: <what>`. Change the plan when it
is wrong, in the same commit as the fix. A failing check loops: diagnose, fix at the cause
with a failing test first, re-run, adjust the plan.

What the handoff reserves is not ruled on. When a reserved item blocks a case: skip that
case, log a `Gap:` line, keep going with everything else, and put it in the report. A
safety mechanism of the user's tools (folder trust, permission prompts, credentials, branch
protection) is always reserved: make the product detect and report it; never write the
setting that disables it, even when that makes a test pass.

### 6. Rehearse, then accept live

Rehearse the acceptance on an intermediate head while the last waves run; final acceptance
on the final head, installed from it. Sandbox only, run-prefixed resources, one fresh
resource per case, one variable per diagnosis, evidence per item in the ledger.
`references/live-acceptance.md`.

### 7. Final review

Whole branch, most capable model, against the criteria and the contract deltas. Split by
architectural area when the diff is too large for one careful read (a ruling). One fix wave
for Critical, Important and fix-now items, re-reviewed by scope; the rest parked with
rulings.

### 8. Clean up, report, hand back

Verify cleanup against the snapshot (step 3 of "Done"). Write the report
(`references/report.md`): what shipped, evidence, every ruling with its cost, gaps and
reserved cases, the exact validation and rollback steps. Tell the user where it is, where
they look first.

### 9. Feedback rounds

When the user rejects part of a shipped design, run the same loop at the size of the
change: a brief with the user's decision verbatim, an implementer in a worktree, a review, a
scoped re-review, integration, and a new plan with lanes when there are several items. A
user correction that reverses a ruling becomes a rule in the next handoff.

## Rationalizations

| Thought | Reality |
|---|---|
| "The migration/install/remote write is irreversible, so I'll leave it for the user to apply" | That is a risk decision, and it is theirs. Ask it in step 2 with your default; build what they allow. |
| "If I don't hear back I'll run the safe scope" | Silence is not an answer. The run starts after the answers. |
| "A gate failed twice, stop the run and write why" | Diagnose and loop. Stop only for a reserved item, and then only that case. |
| "The plan doesn't answer this, stop and ask" | Rule by the criteria, log the cost, continue. |
| "Two tasks touch the same file, run them serially" | Split ownership of the file in the lane table first; serialize only what cannot be split. |
| "Writing the trust key makes the live test pass" | It disables the user's safety mechanism. Detect, report, log the gap. |
| "The web repository needs a new field in the shared schema; I'll add it there myself" | A cross-repository contract changes only through the parent: ask, wait on that item, keep the rest moving. |
| "A sub-orchestrator asked something; I'll forward it to the user" | You answer it from the criteria. Only a reserved item becomes a gap in the report. |
| "I remember which tasks are merged" | After compaction, the ledger and `git log` are the truth. |
| "The worktree can go later" | A wave is not done while its worktrees or branches exist. |

## Red flags

- A plan step that says "the user installs", "the user checks", "after a day of use".
- A message to the user that announces a scope instead of asking.
- A ruling without "cost if wrong".
- A delegate that touched a service, a home directory or a remote.
- A report without the rollback steps.
