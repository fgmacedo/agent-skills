# Final report template

Written for a person who was away and will spend minutes, not hours. Facts with evidence; the
ledger holds the full outputs. Commit it next to the plan.

The file starts at the first merge as a live report holding only the Progress section
(`progress.md`), kept current during the run. At the end, add the sections below after it,
and the progress shows the final state.

~~~markdown
# <change> report

Integration branch `<branch>`, head `<sha>` (installed as `<version>`), <n> commits on top of
`<plan-commit>`. Run window: <start> to <end> (<timezone>). Ledger: `<path>`.

## Progress

<progress-py-show-ascii-and-progress-py-mermaid>

## Tasks

<progress-py-table>

## What shipped

<One bullet per user-visible capability, in the user's terms. Then "Added during the run,
beyond the plan", each with the number of its ruling below.>

## Acceptance evidence

| # | Result |
|---|---|
| <criterion or item> | <test name PASS / command and the decisive part of its output> |

<Say which items the plan allowed two ways and which way they passed.>

## Rulings

Each with what it costs if wrong. Numbered, so the user can answer by number.

1. <ruling>. Cost: <cost>.

## Gaps and reserved decisions

<What does not work yet, what was left for later, and every case the run skipped because it
was reserved, with what the user must decide.>

## Your validation

1. <the exact commands to confirm the install and health>
2. <what to look at, and where>
3. <files the run changed outside the repository, each with its backup, and what to keep or delete>
4. <how to turn automation back on>

To go back to the previous state: <the exact restore steps, with paths>.
~~~
