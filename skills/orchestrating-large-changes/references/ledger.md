# The ledger

`ledger.md` in the run directory is the run's memory: one line per state change, in the
user's zone, a `## YYYY-MM-DD` heading per day. After compaction or a crash, the next
session reads it and `git log` and resumes. The board and the report's progress are
generated from it.

## Lines

~~~markdown
# Ledger: <change>

Plan <plan-dir>. Handoff <path>. Integration <branch> at <worktree>, start <sha>. Run dir <path>. Times in <zone>.
Checks: lane <cmd>; integration <cmd>, cap 2. Baseline green <n> times in parallel on <sha>.

## 2026-10-21
- 19:05 P0 passed plan review: 0 Critical, 3 Important applied to T0 in 1a2b3c4
- 19:10 T0 merged 9c8d7e6
- 19:12 T1,T2,T3 dispatched opus
- 19:52 T1 reported 21a25b0; review sent: DST hour in Cron.Next, nil Transient
- 20:01 T1 fix 1: DST hang (Important), Transient nil panic (fix-now)
- 20:10 T1 clean 4e65a77, inline re-review
- 20:14 T1,T3 merged 2ca6ce1
- 20:31 gate green on 2ca6ce1 after T1,T3
- 21:31 Ruling: no cache for the sweep's Check - measured 0.5-3 s per sweep - cost if wrong: seconds per sweep
- 21:40 Gap: folder trust prompt - reserved by rule 12 - live case 4 skipped - user decides the trust setting
- 23:05 R passed rehearsal on 7f8e9d0
- 23:20 A/A3: <product> status -> "paused: 0 repositories"
~~~

The form a script reads: `- HH:MM <ids> <event> <details>`, ids comma-separated, events:

| Event | Status after it |
|---|---|
| `dispatched`, `started` | in progress |
| `reported`, `clean` | in review |
| `fix <n>` | in progress (counted as a fix round) |
| `merged`, `passed` | done |
| `held`, `dropped` | held, dropped (the details are the reason) |

Write each line with `$L add <ledger> <text>` (`$L` below) in the command that acts (the
dispatch, the merge, the gate), never in a turn of its own: 58 turns of a measured run did
nothing else and cost 11% of the orchestrator's input tokens.

Other lines (`gate` per batch, `Ruling:`, `Gap:`, acceptance evidence
`A/<item>: <command> -> <output>`) serve resume and the report; the script ignores them. A delegate's ruling is copied with its author: `Ruling: (T7's) ...`.
"Cost if wrong" is concrete ("a rebase in cli.go", "the user sees the error without the
restart command"); "none" only when true. A ruling that touches a reserved item is a `Gap:`
with what was skipped and what the user must decide.

## Generated views

~~~bash
L="python3 <skill-dir>/scripts/ledger.py"
$L show  <plan-dir>/core.md <run-dir>/ledger.md --repo <integration-worktree>   # the board
$L times <plan-dir>/core.md <run-dir>/ledger.md        # wall time per task, fix rounds
$L mermaid <plan-dir>/core.md <run-dir>/ledger.md      # graph colored by status
$L table <plan-dir>/core.md <run-dir>/ledger.md --link <plan-dir>/tasks   # task table for the report
$L add <run-dir>/ledger.md T7 merged 2ca6ce1 --tz <zone>   # append a line, now, in the user's zone
~~~

The graph is the first Mermaid flowchart in `core.md`; a node with a file in `tasks/` or
an id like `T7` is a task, any other a gate. End every loop turn with `show` in a code
block:

```text
workflows engine  ·  ledger 2026-10-21 22:45  ·  head 4b303ac

Plan         [███████░░░░░░░░░░░░░]   9/27  merged  ·  4 active, 1 held
  Release 1  [█████████████░░░░░░░]   8/12  merged  ·  2 active
Gates        ✔ plan review  ◎ rehearsal

  1-3  ✔ all 7 merged
    4  ✔ T6  ◐ T7  ◎ T10  ⏸ T9
    5  · T11  · T12
 6-11  · T13  · T14  · R  · A

Next up   T11
· not started   ◐ in progress   ◎ in review   ✔ merged   ⏸ held   ✗ dropped
```

Rows are dependency levels; settled leading levels and untouched trailing levels collapse.
`--ascii` swaps glyphs; color is on in a terminal (`--color always|never`).

## Resume protocol

1. Read the handoff and the ledger from disk.
2. `git log --oneline <start>..HEAD`, `git worktree list`, `git branch --list '<prefix>/*'`.
3. Where the ledger and git disagree, git wins; append a line saying what was corrected.
4. Collect delegates that finished meanwhile (report files, branches) before dispatching.
   Never re-dispatch a task with a `merged` line or a branch holding its commits.
