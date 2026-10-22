# Delegation: lanes, reviews, merges

With superpowers, superpowers:subagent-driven-development owns the per-task loop. This file
overrides it where they differ: parallel lanes, the model policy, reviews against named
concerns, re-reviews through the same reviewer, batch merges.

## Roles

| Role | Model | Reads |
|---|---|---|
| Plan reviewer | most capable | the whole plan, the code |
| Implementer, fixer | most capable (cheap tier only for a docs-only task) | `implementer.md`, core, its task file, the contract sections it names |
| Task reviewer | most capable | `reviewer.md`, core, the task file, `git diff`, the report |
| Final reviewer | most capable | criteria, core, `contracts.md`, the branch diff (or one area) |
| Live acceptance | the orchestrator | |

The orchestrator never implements a task and never lets a delegate touch the outside world
(installs, services, remote writes, the user's homes).

## Worktrees

One worktree and branch per task, created by the orchestrator from the integration head.
With Orca, as a child of the session's worktree, so the user sees them grouped:
`orca worktree create` without `--no-parent` (or `--parent-worktree path:<session-worktree>`
from outside it); an existing one with `orca worktree set --worktree path:<wt>
--parent-worktree path:<session-worktree>`. Without Orca, `git worktree add <path> -b
<branch> <integration-head>`. Report and review paths are absolute, in the run directory.

## Starting a task

A task starts when every contract it consumes exists in code, merged or in the producer's
types-only first commit (branch from that commit), and its files do not overlap any task in
flight, or the overlap is split by ownership in both task files. Producers merged or not. Log the start; a late producer change costs a rebase, cheap next to
an hour of waiting.

## Dispatch

~~~text
Implement <id> of <change>. Read <run-dir>/implementer.md, then <plan-dir>/core.md and <plan-dir>/tasks/<id>-<slug>.md.
Worktree <path>, branch <branch>. Report <run-dir>/reports/<id>.md.
~~~

## implementer.md

~~~markdown
# How you work

Plan files are read from <integration-worktree>/<plan-dir>; contracts.md there is current.
Read only the contracts.md sections your task names.

- Work only in your worktree and branch. Never push, switch branches or `git stash`.
- Edit the task's Files, tests beside them, and call sites a signature change forces.
  A contract in another task's Files is not yours to change: report the need as a concern.
- Nobody answers questions. Decide by the criteria and the constraints, write
  `Ruling: <what> - <why> - cost if wrong: <what>` in the report, finish DONE_WITH_CONCERNS.
- Never touch the outside world: no remote writes, installs, services, or edits under the
  home directory outside your worktree. Tests use temporary homes.
- Fixtures from real data carry no personal data, and the script that reduced them is not
  committed beside them.
- Tests first: write each scenario's test, see it fail, implement, see it pass.
- While iterating, test only the packages you touch.

Before you report:
1. Attack each Review focus scenario your task touches against real local systems your
   test starts in temporary directories or ports (a real git repository, a real store, a
   real server binary), not only through your tests.
2. Measure what your code costs per call or per sweep at realistic scale (<sizes>) and put
   the number in the report.
3. When you replace behavior, a differential test against the old code path passes.
4. Rebase onto the integration head (`git -C <integration-worktree> rev-parse HEAD`), then
   run the full gate once: <full-gate>.
5. Any exported name you removed or renamed is in a declared contract delta.

Report file, short: commits, rulings, contract deltas (ADDED/MODIFIED/REMOVED/RENAMED with
full text), concerns, cost measured, gate result. Reply in under 10 lines: status (DONE |
DONE_WITH_CONCERNS | BLOCKED), commits, gate, report path.
Resumed with findings: fix, re-run the covering tests and the gate, append to the report.
~~~

## Review

Every dispatch names the concerns to adjudicate. A reviewer told what to decide finds the
real bug; one told "review this" restates the diff.

~~~text
Review <id>. Read <run-dir>/reviewer.md, <plan-dir>/core.md, <plan-dir>/tasks/<id>-<slug>.md, the report <run-dir>/reports/<id>.md.
Diff: git -C <worktree> diff <integration-branch>...<head> (three dots: from the merge base, valid after rebases). Findings to <run-dir>/reviews/<id>.md.
Adjudicate: <for each, one line: the implementer's concern or ruling, a review focus scenario, a cost claim; "decide bug or accepted difference, give the fix and the file">.
~~~

~~~markdown
# How you review

Read-only in the task's worktree; you may run tests there. Check: every scenario has its
named test and it fails without the change; the review focus scenarios the task touches,
tried against real systems; the declared contract deltas are needed, exact, and break no
task file; each named concern decided. Severity: Critical (wrong behavior, data loss, a
broken constraint), Important (a missing scenario test, an unusable contract), Minor.
Mark a Minor fix-now only when cheap and otherwise carried into later tasks.
Findings file: per finding, severity, file:line, failure scenario, fix. Reply in under
6 lines: CLEAN | NEEDS FIXES, counts, path.
~~~

**Fix rounds.** The findings go to the implementer that holds the context: resume it with
SendMessage by its agent id. The re-review goes to the same reviewer the same way, scoped to
the findings and the fix diff, appended to the same review file. A trivial fix (one line,
a test name, a message) the orchestrator re-reviews inline by reading the diff, and logs
it; a fix that touches a contract is never trivial. A flaw found later in a
merged task goes, by ruling, to whoever holds that context: the task in flight that touches
those files, or a fresh fixer.

**Named teammates.** On Claude Code with agent teams, a *named* agent's final text does not
come back; only an idle signal does. Use unnamed agents and resume them by id. When you name
one, its prompt must say: "When done, send your full report with SendMessage to
<orchestrator-name>." An idle one has not failed: collect its branch and report first.

## Merging in batches

Merge every task reviewed clean, back to back, in graph order (then by task number), then
gate once:

~~~bash
git merge --no-ff <branch>       # each task in the batch
<fold its contract deltas into contracts.md; amend the merge commit>
<fast-gate>                      # seconds, after each merge
<full-gate>                      # once per batch, with the expensive variants
git worktree remove <path>; git branch -d <branch>    # each merged task
~~~

On a red full gate, bisect the batch's merge commits (`git bisect` over `--first-parent`),
send the fix to the task that broke it, and keep the other merges. Resolve conflicts in the
integration branch only when mechanical (imports, adjacent additions; never a contract); anything that changes behavior goes back to a
fixer. A task is not done while its worktree or branch exists.

## Final review

Whole branch, most capable model, against the criteria, core and `contracts.md`. Too large
for one careful read: split by architectural area, log the split as a ruling (a cross-area
issue can fall between them). Critical, Important and fix-now go to one fix batch,
re-reviewed by scope; the rest is parked with a ruling.
