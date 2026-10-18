# Progress

A run can take hours. The user glances at the terminal or opens the report and must see at
once how much of the plan is done, what is moving, what is held and what is next. One state
file holds the progress; `scripts/progress.py` renders it for the terminal and generates the
report's sections. Nobody edits the graph or the tables by hand.

## The state file

`progress.json` in the plan workspace, next to the ledger (git-ignored). Only the
orchestrator writes it, always through the script.

~~~bash
P="python3 <skill-dir>/scripts/progress.py"
S=<plan-workspace>/progress.json

$P sync $S --plan <plan-path> --title "<change>"       # once, and after every plan change
$P add  $S P0 --title "plan review" --gate --before T1,T2,T6
$P add  $S R --title "rehearsal" --gate --after T13 --before A
$P set  $S T3 --status wip                              # dispatched
$P set  $S T3 --status review                           # implementer reported
$P set  $S T3 T4 --status done                          # merged
$P set  $S G1 --release "Release 1" --note "moved in, ruling 4"
$P set  $S I2 --status held --note "until L2"
$P set  $S T9 --status dropped --note "ruling 12"
~~~

- `sync` reads the plan's task headings (prefix `Task `, change with `--prefix`) and its
  first Mermaid flowchart: edges become dependencies, subgraphs become releases, graph nodes
  without a task heading become gates. Statuses survive a re-sync; a node gone from the plan
  becomes dropped. So the plan's dependency graph is the single source, and a ruling that
  changes it changes the plan, then re-syncs.
- Gates the plan's graph does not draw (plan review, rehearsal, whole-branch reviews, live
  steps) are added with `add --gate`, with `--after` and `--before` to place them.
- Statuses: `todo`, `wip`, `review`, `done`, `held`, `dropped`. A gate is `done` when it
  passes. Put the reason of a hold, a move or a drop in `--note`, naming the ruling.
- Update it right after the ledger entry that changes a state, never before.

## Every loop beat ends with the board

Each turn of the run's loop ends its message with the current board, in a code block, so
the last thing on the terminal is always the progress:

~~~bash
python3 <skill-dir>/scripts/progress.py show <plan-workspace>/progress.json --repo <integration-worktree>
~~~

Example, mid-run:

```text
Timings, brief-first, profile ontology  ·  updated 2026-10-18 12:24 -03  ·  head 4b303ac

Plan         [███████░░░░░░░░░░░░░]   9/27  merged  ·  4 active, 1 held
  Release 1  [█████████████░░░░░░░]   8/12  merged  ·  2 active
  Release 2  [█░░░░░░░░░░░░░░░░░░░]   1/15  merged  ·  2 active, 1 held
Gates        ✔ track D: D5 merged  · review 1  ✔ track D: D8 merged  · review 2

    1  ✔ all 4 merged
    2  ✔ S1  ✔ T1  ✔ S4  ⏸ I2  ◎ G1
    3  ✔ S2  ✔ S3
    4  ✔ R1t  ✔ T2
    5  ◎ W1
    6  · RV1
    7  · L1
    8  · L2
    9  ◐ R2t
   10  ◐ R3  · P1
11-21  · P2  · P3  · P4  · P5  · W2  · W3  · W4  · X1  · RV2  · L3  · L4

Held      I2 (until L2)
· not started   ◐ in progress   ◎ in review   ✔ merged   ⏸ held   ✗ dropped
```

The numbered rows are dependency levels: a task sits one level after its latest input.
Leading levels where everything is merged, and trailing levels nobody started, collapse into
one line each. `Next up` lists tasks whose inputs are all merged and that nobody started. `--ascii` swaps the glyphs and bars for plain
characters; color is on in a real terminal and off when piped (`--color always|never`).

In a multi-repository run, each child keeps its own state file and board. The parent's
state has one task per repository plus the joint gates, and its notes carry the child's
count ("7/11 merged").

## The report's sections

The report (`report.md`) exists from the first merge and is regenerated from the state file
on every update, committed on the integration branch:

1. **Bars and levels**: `show --ascii --color never --repo <worktree>`, in a `text` block.
2. **Task graph**: `mermaid` prints the plan's graph with the gates, one subgraph per
   release, and the nodes colored by status (green merged, yellow in progress or review,
   grey not started, dashed red held, dashed grey dropped, blue gates not yet passed).
   Paste it as printed; add the legend as a plain sentence after it.
3. **Tasks**: `table --link <plan-path-from-the-report>` prints one row per task in plan
   order: code, title linked to the task's heading in the plan, release, status with its
   note. Open the section with a link to the spec. A plan without one heading per task gets
   no link: write one sentence of what each task delivers and its acceptance check instead.
4. **Merged so far**, from the ledger: task (linked like the Tasks table), commits, review
   outcome and fix rounds.
5. **Rulings to review**: the few the user should read first, one line each with its cost;
   the ledger has the rest.

## Rendering rules

The report is read in Markdown previews that refuse HTML, so: no HTML outside code blocks,
no comment tags, no fence nested in another fence, placeholders without spaces. The
generated graph already quotes every label and uses subgraph ids that cannot collide with
task ids.
