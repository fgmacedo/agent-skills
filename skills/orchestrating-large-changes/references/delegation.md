# Delegation: roles, worktrees, review packages

With superpowers, superpowers:subagent-driven-development owns the per-task loop
(implementer, task review, fix rounds capped at five, scoped re-review, parking minors) and
its prompt templates. This file adds what parallel lanes need on top of it. Without
superpowers, use the contracts below as the whole loop.

## Roles and model tiers

| Role | Model | Gets | Returns |
|---|---|---|---|
| Plan reviewer | most capable | criteria, spec, plan, handoff, code | findings file, counts |
| Implementer | cheap tier for a mechanical one- or two-file task; standard or most capable for multi-file, contract-producing or subtle work | shared "how you work" file, task brief, lane row, constraints, its worktree and branch, report path | short status contract; full report in a file |
| Task reviewer | scaled to the diff's size and risk | brief, report, review package | verdict and findings |
| Fix-round re-reviewer | cheap to mid tier | findings, fix report, fix diff | ADDRESSED / NOT ADDRESSED per finding |
| Final reviewer | most capable | criteria, plan, contract deltas, whole-branch diff (or one area of it) | findings file |
| Live acceptance | the orchestrator itself | | ledger entries |

The orchestrator never implements a task and never lets a delegate touch the outside world
(installs, services, remote writes, the user's homes). Everything live runs in the
orchestrator, one step at a time, so one agent holds the safety rules.

## Shared files instead of long prompts

Write once in the plan workspace, point every dispatch at them:

- `implementer-common.md`: how every implementer works (below);
- `constraints.md`: the plan's Global Constraints and the safety rules, verbatim;
- `waves.md`: the lane table;
- `task-<n>-brief.md`: the task's requirements with exact values to use verbatim;
- `contract-deltas.md`: every change a task made to an interface the plan wrote, appended by
  the orchestrator after each review, read by later implementers and the final reviewer.

A dispatch is then five lines:

~~~text
You are implementing Task <n> of the <change> plan (<one-line goal>).
WS=<plan-workspace>
Read first: $WS/implementer-common.md, then $WS/task-<n>-brief.md, the T<n> row of $WS/waves.md, and $WS/constraints.md.
Your worktree: <scratch>/wt/t<nn> (branch <prefix>/t<nn>-<slug>). Work and commit only there.
Report file: <report-path>
~~~

## implementer-common.md

~~~markdown
# How you work (every implementer)

- Work only in your own worktree and branch. Never touch another worktree, never push, never switch branches.
- Edit only the files your lane row's "May touch" allows, plus tests beside them. If the task truly needs another file, edit it minimally and say so in the report.
- Nobody answers questions. When the brief is ambiguous or wrong against the code, decide by the spec and the success criteria, write "Ruling: <what> - <why> - <cost if wrong>" in the report, and finish as DONE_WITH_CONCERNS. BLOCKED only if no reasonable path exists.
- Never touch the outside world: no remote writes, no installed binary, no services, no edits under the home directory outside your worktree. Tests use temporary homes.
- Before committing, run <gate-command> and get it green. Each commit is green.
- You do not dispatch subagents.
- Self-review your diff before reporting.

Report: write the full report (what you did, test commands with trimmed output, files changed, rulings, concerns) to the report file. Then reply with only, under 15 lines: Status (DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT), commits (short SHA and subject), one-line test summary, concerns, report path.

If resumed with review findings: fix them, re-run the covering tests, append a fix report to the same file, reply with the same short contract.
~~~

## Where a delegate can write

A delegate started with the harness's own worktree isolation may be unable to write outside
that worktree, so a report path in the orchestrator's workspace fails. Pick one before
dispatching:

- create the worktree yourself (`git worktree add <scratch>/wt/t<nn> -b <branch> <base>`) and
  give the delegate the absolute report path in the plan workspace; or
- with harness isolation, name a report path inside the delegate's worktree, untracked, and
  copy it into the plan workspace when the delegate returns (or take the report from its
  final message and write it yourself).

Either way, record in the ledger where the report is.

## Review packages

Reviewers read files, not your context. Before dispatching a review, write the diff once:

~~~bash
git -C <worktree> log --oneline <base>..<head> > <ws>/review-<base>..<head>.diff
git -C <worktree> diff --stat <base>..<head> >> <ws>/review-<base>..<head>.diff
git -C <worktree> diff -U10 <base>..<head> >> <ws>/review-<base>..<head>.diff
~~~

The review dispatch names: the brief, the report, the package path, base and head, the
checkout to inspect read-only, and the output path. The reviewer replies with the verdict
and the path; you read the findings file only when the verdict is not clean.

## Named teammates

Some harnesses offer persistent named agents (agent teams). On Claude Code with agent teams
enabled, a named agent's final text does not come back to the caller; only an idle signal
arrives, and the work stays in its own transcript. Use unnamed subagents for one-shot work.
When you name one, the spawn prompt must say: "When done, send your full report with
SendMessage to <orchestrator-name>, in the message body." If one goes idle without
reporting, collect its branch and report file before re-sending anything.

## Integration

After each wave's tasks are complete (reviewed clean):

~~~bash
git switch <integration-branch>
git merge --no-ff <prefix>/t01-<slug>      # task order, producers first
<gate-command>                              # the wave's integration check, from the plan
git worktree remove <scratch>/wt/t01
git branch -d <prefix>/t01-<slug>          # -d refuses an unmerged branch: a useful check
~~~

Resolve conflicts in the integration branch only when they are mechanical (import blocks,
adjacent additions); anything that changes behavior goes back to a fix task branched from
the integration head. Worktrees are ephemeral: a worktree exists only while its task runs,
and a wave is not done until `git worktree list` and `git branch --list '<prefix>/*'` show
nothing of it.

## Final review

On the most capable model, over the whole branch against the criteria and the plan. When the
diff is larger than one reviewer can read carefully, split it into areas that follow the
architecture (domain and core; transport and clients; CLI, install and docs), give each the
plan and the contract deltas, and log the split as a ruling with its cost (a cross-area issue
can fall between them). Every Critical and Important finding and every minor marked fix-now
goes to one fix wave, re-reviewed by scope. The rest is parked in the ledger with a ruling.
