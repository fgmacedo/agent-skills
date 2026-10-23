# Delegation: lanes, reviews, merges

With superpowers, superpowers:subagent-driven-development owns the per-task loop; this file
overrides it on lanes, models, reviews and merges.

## Roles

| Role | Model | Reads |
|---|---|---|
| Plan reviewer | most capable | the whole plan, the code |
| Implementer, fixer | most capable (cheap tier only for a docs-only task) | `implementer.md`, core, its task file, the API docs of the packages it consumes |
| Task reviewer | most capable | `reviewer.md`, the task file, its review focus lines, `git diff`, the report |
| Final reviewer | most capable | criteria, core, the branch diff (or one area) |

The orchestrator runs live acceptance, never implements a task, and never lets a delegate
touch the outside world (installs, services, remote writes, the user's homes).

## Worktrees

One worktree and branch per task, created by the orchestrator from the integration head.
With Orca, as a child of the session's worktree (`orca worktree create` without
`--no-parent`), so the user sees them grouped; without, `git worktree add <path> -b
<branch> <integration-head>`. Report and review paths are absolute, in the run directory.

## Starting a task

A task starts once T0 is merged and its files do not overlap a task in flight (or both
task files split the overlap by ownership). It waits only on a graph edge.

## Dispatch

~~~text
Implement <id> of <change>. Read <run-dir>/implementer.md, then <plan-dir>/core.md and <plan-dir>/tasks/<id>-<slug>.md.
Worktree <path>, branch <branch>. Report <run-dir>/reports/<id>.md.
~~~

## implementer.md

~~~markdown
# How you work

Plan files are in <plan-dir>, outside the repository; never copy them in. Contracts are
code: read the API docs of what you consume (<doc-command>).

- Work only in your worktree and branch. Never push, switch branches or `git stash`.
- Edit the packages your task owns, tests beside them, and call sites a signature change
  forces. A contract another task owns is not yours to change: report the need as a concern.
- Register through the registration points; never edit a shared list.
- Nobody answers questions. Decide by the criteria and the constraints, write
  `Ruling: <what> - <why> - cost if wrong: <what>` in the report, finish DONE_WITH_CONCERNS.
- Never touch the outside world: no remote writes, installs, services, or edits under the
  home directory outside your worktree. Tests use temporary homes.
- Tests first: turn each stub skipped with your task id into the real test, see it fail,
  implement, see it pass. Done means no stub with your id is left.

Before you report:
1. Attack each review focus line your task touches against real local systems your
   test starts in temporary directories or ports (a real git repository, a real store, a
   real server binary). Break each new test once (revert the line it guards); it fails.
2. Measure what your code costs per call or per sweep at realistic scale (<sizes>) and put
   the number in the report.
3. When you replace behavior, a differential test against the old code path passes.
4. Rebase onto the integration head (`git -C <integration-worktree> rev-parse HEAD`), then
   run the lane check: <lane-check>. Never the integration gate; the orchestrator runs it.

Report file, short: commits, rulings, concerns, cost measured, lane check result, and the
API-diff output of the contract packages (<api-diff-command>), pasted, not described.
Reply in under 10 lines: status (DONE | DONE_WITH_CONCERNS | BLOCKED), commits, check,
report path. Resumed with findings: fix, re-run the lane check, append to the report.
~~~

## Review

Every dispatch names the concerns to adjudicate. A reviewer told what to decide finds the
real bug; one told "review this" restates the diff.

~~~text
Review <id>. Read <run-dir>/reviewer.md, <plan-dir>/tasks/<id>-<slug>.md, review focus <RF lines>, the report <run-dir>/reports/<id>.md.
Diff: git -C <worktree> diff <integration-branch>...<head> (three dots: from the merge base, valid after rebases). Findings to <run-dir>/reviews/<id>.md.
Adjudicate: <one line each: a concern or ruling of the implementer, a review focus line, a cost claim; "decide bug or accepted, give the fix">.
~~~

~~~markdown
# How you review

Read-only in the task's worktree; you may run tests there. Check: no stub with the task
id is left, and each test fails without the change; the review focus lines the task
touches, tried against real systems; each change in the API diff is needed and owned by
this task; each named concern decided. Severity: Critical (wrong behavior, data loss, a
broken constraint), Important (a test that cannot fail, an unusable contract), Minor.
A Minor is fix-now or dropped. One that matters later is carried as a skipped test in the
owning package, named for the finding and the task that fixes it; never as a note.
Findings file: per finding, severity, file:line, failure scenario, fix. Reply in under
6 lines: CLEAN | NEEDS FIXES, counts, path.
~~~

A reviewer agent reviews every task that changes code (Lite: the orchestrator, inline): in
the measured run 80% of Critical and Important findings were behavior bugs no compiler
catches. Irreversible or safety-critical code (a migration of user data, a permission
check, a destructive command) also gets an adversarial reviewer told only to break it.

**Fix rounds.** Findings go to the implementer that holds the context, resumed by agent id;
the re-review to the same reviewer, scoped to the findings and the fix diff, appended to
the same file. The orchestrator re-reviews a trivial fix (one line, a name, a message)
inline; a fix that changes the API diff is never trivial. A flaw found later in a merged
task goes, by ruling, to the task in flight on those files or a fresh fixer.

**Named teammates.** On Claude Code with agent teams, a *named* agent's final text never
comes back, only an idle signal. Use unnamed agents, resumed by id; a named one's prompt
says "When done, send your full report with SendMessage to <orchestrator-name>." Idle is
not failed: collect its branch and report first.

## Merging in batches

Merge every task reviewed clean, back to back, in graph order, then gate once. The merge
is the contract update; nothing is folded by hand. `$L`: `references/ledger.md`.

~~~bash
git merge --no-ff <branch> && <build> && $L add <ledger> <id> merged $(git rev-parse --short HEAD)
<integration-gate> && $L add <ledger> gate green on $(git rev-parse --short HEAD)   # once per batch
git worktree remove <path>; git branch -d <branch>    # each merged task
~~~

Heavy test runs (integration gate, flake hunt) share a run-wide cap of 2: 8 concurrent
full suites in a measured run timed out and produced 18 flake reports.

On a red integration gate, bisect the batch's merge commits (`git bisect` over `--first-parent`),
send the fix to the task that broke it, and keep the other merges. Resolve a conflict in the
integration branch only when mechanical (imports, adjacent additions; never a contract);
anything else goes back to a fixer. A task is not done while its worktree or branch exists.

## Final review

Whole branch against criteria and core; split by area when too large (a cross-area issue
can fall between them). Critical, Important and fix-now go to one fix batch.
