# Final report template

For a person who was away and will spend minutes. Facts with evidence; the ledger holds the
full outputs. Commit it next to the plan. Generate the progress parts with
`scripts/ledger.py` (`show --ascii --color never`, `mermaid`, `table`, `times`).

~~~markdown
# <change> report

Branch `<branch>`, head `<sha>` (installed as `<version>`). Run <start> to <end> (<zone>). Ledger `<path>`.

## Progress
<show, in a text block; mermaid graph; task table; wall-time table>

## What shipped
<one bullet per user-visible capability; then "Added during the run", each with its ruling number>

## Acceptance evidence
| # | Result |
|---|---|
| <criterion or item> | <test PASS, or command and the decisive part of its output> |

## Rulings
Numbered, so the user can answer by number. Read first: <the few that matter>.
1. <ruling>. Cost if wrong: <cost>.

## Gaps and reserved decisions
<what does not work yet; every case skipped because reserved, with what the user must decide>

## Your validation
1. <commands to confirm the install and health>
2. <files changed outside the repository, each with its backup>
3. <how to turn automation back on>

To go back: <exact restore steps, with paths>.
~~~
