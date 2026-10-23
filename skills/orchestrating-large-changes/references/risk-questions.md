# Risk questions: asked once, after the plan

The user owns every decision about risk. Ask them all in one message, after the plan exists
and before the run, so the run never waits on a person.

1. The questions come from every task that touches something outside the repository: a
   binary, a service, a config or home directory, a database, a remote API, another tool.
2. One message, each question with your default and why; the user answers by exception
   ("all defaults, except 4"). The harness's question tool for the few real alternatives.
3. Every human stop point ("the user installs", "after a day of use") becomes a criterion
   an agent evaluates. What truly needs the person is reserved and worked around.
4. Prepare what the answers allow: backup with checksums, sandbox, snapshot.
5. Write the answers into the handoff, so a fresh agent applies them.

Ask only the rows the plan touches.

| # | Ask | Typical default |
|---|---|---|
| 1 | Window: until when is the run alone; is the machine in use? | Until the stated return; unused |
| 2 | Done: merged where, installed or not, which live proofs, which report? | Integration branch green, installed from it, every item proven, report written |
| 3 | Remote writes: which repositories, projects, accounts, services? | Only a sandbox the run controls; reads anywhere |
| 4 | Pull requests: where may the run push and open them, draft or ready? Who merges? | Draft PRs on the repositories the plan changes; never merge |
| 5 | Live tests: a sandbox; who plays the other actors? | Private sandbox with scripted actors, created before the run |
| 6 | Automation that acts on its own: what may run during the window? | Paused everywhere but the sandbox; paused at the end |
| 7 | Install and restart: may the run do it, through what? | Yes, only through the product's installer and service labels |
| 8 | The user's data: what must survive, where is the backup? | Backup now, read-only, checksums compared at the end; migrations read a copy |
| 9 | The user's own things the run never touches | Nothing the run did not create is closed, renamed, moved or deleted |
| 10 | Run-owned prefix | `<project>-e2e-*` |
| 11 | Config and home files that may change, and through what | Only through the installer, which backs up each file first |
| 12 | Safety mechanisms of the user's tools (folder trust, prompts, credentials, signing, branch protection) | Never bypassed; detected and reported; reserved |
| 13 | Processes the run may kill | Only those it started, by PID; services through their manager |
| 14 | Compatibility: old behavior, formats, clients | Ask; the answer reshapes the plan |
| 15 | Spend: models, paid APIs, CI minutes | Most capable model for every task that changes code and every review; cheap tier for docs |
| 16 | Multi-agent opt-in: subagents, agent teams, workflows | Yes |
| 17 | Reserved: what the run never decides alone | 3, 9, 12 and anything irreversible outside the sandbox |
| 18 | Hand-back: where the report goes, how the user learns the run ended | Report in the run directory, its path where the user looks first; a summary in each PR body |

Not here: design questions the plan settled, and anything a measurement in the run can
settle. Those are rulings.
