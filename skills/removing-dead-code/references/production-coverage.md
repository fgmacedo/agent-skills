# Dynamic detection: coverage in production across many services

Static tools cannot prove an endpoint, a task, a cron job or a whole module
dead. Only execution data can, and when one code base ships as many services
(one uwsgi API, ~50 worker Deployments and ~90 CronJobs on Kubernetes is the
reference case) only the **union** of execution data across all of them proves
anything. A function the API never calls is routinely the heart of a cron job.

This document covers four techniques, then the full design for coverage.py
across many services.

## Techniques

| Technique | What it proves | Cost | Python 2.7 |
|---|---|---|---|
| coverage.py in production | every executed line, per service | C tracer, roughly 1.3x to 2x CPU on web workloads [unverified] | coverage 5.5 |
| Tombstone or probe | one suspect function was or was not called, with a timestamp | near zero | own code |
| `sys.setprofile` recorder | set of `(file, function)` called at least once | low, no line data | own code |
| py-spy sampling | functions seen on the stack | out of process, no code change | 2.3-2.7 supported |
| Access logs, APM, task counters | hits per route and per task | already collected | n/a |

### Tombstones and probes

A tombstone is a cheap marker in a suspected-dead function. Deploy, wait a full
cycle, delete the function if the marker never fired. Write the helper yourself;
the old PyPI package `tombstones` 0.1 (2015) is not worth using.

```python
import logging
log = logging.getLogger("tombstone")

def tombstone(tag):
    log.warning("TOMBSTONE %s", tag)
    statsd.increment("tombstone", tags=["tag:%s" % tag])

def legacy_export(rows):
    tombstone("2026-10-12:billing.legacy_export")
    ...
```

Query logs or metrics for the tag after the window. The tag includes the date
the tombstone was planted so the window is visible in the commit message.

Dark removal is the next step for routes and tasks: put the body behind a flag
that returns 410 or raises `NotImplementedError`. Flipping the flag back is an
instant rollback. Delete one release later.

Origins: David Schnepper, "Isn't That Code Dead?", Velocity 2014 (cited by Andy
Snell's Zombie Hunt, https://github.com/andysnell/zombie-hunt); Bugsnag
(https://www.bugsnag.com/?p=1862); Michael Feathers, "Scythe: Coverage in
Production to Find Dead Code", named probes that touch a zero-length file to
record the last hit time (https://michaelfeathers.silvrback.com/scythe-using-coverage-in-production-to-find-dead-code).

### `sys.setprofile` recorder

When line coverage is too expensive, record only the first call of each
function. Flush the set periodically.

```python
import sys
import threading

SEEN = set()

def _profile(frame, event, arg):
    if event == "call":
        code = frame.f_code
        key = (code.co_filename, code.co_name, code.co_firstlineno)
        if key not in SEEN:
            SEEN.add(key)

def install(flush, interval=300):
    sys.setprofile(_profile)
    threading.setprofile(_profile)

    def loop():
        while True:
            threading.Event().wait(interval)
            flush(sorted(SEEN))

    t = threading.Thread(target=loop)
    t.daemon = True
    t.start()
```

Cheap enough for production on 2.7. Same post-fork rule as coverage.py below.

### py-spy

```bash
py-spy record --pid "$PID" --format raw --subprocesses --nonblocking --duration 600 -o samples.txt
```

Aggregate function names over weeks. Sampling proves live only; absence of
samples never proves dead.

## coverage.py across many services

### 1. Collection: in process, at the common entry point, post-fork

All services share one code base and one entry point module (the WSGI app
factory, the worker bootstrap, the cron `main`). Import
`scripts/coverage_bootstrap.py` there and call `start()` **after** the process
has forked. Nothing happens unless `DEADCODE_COVERAGE=1` is set, so the same
image serves every service and collection is switched on per Deployment.

```python
import coverage_bootstrap

def upload(path):
    key = "coverage/%s/%s/%s" % (SERVICE_NAME, POD_NAME, os.path.basename(path))
    bucket.upload_file(path, key)

recorder = coverage_bootstrap.start(upload=upload)
```

Equivalent to:

```python
cov = coverage.Coverage(data_file="/var/coverage/.coverage", data_suffix=True,
                        source=["mypkg"], concurrency="thread")
cov.start()
```

Post-fork hooks:

```python
# uwsgi, with --lazy-apps the app loads in each worker, so start() at import time is already post-fork
from uwsgidecorators import postfork

@postfork
def _start_coverage():
    coverage_bootstrap.start(upload=upload)
```

```python
# gunicorn.conf.py
def post_fork(server, worker):
    import coverage_bootstrap
    coverage_bootstrap.start(upload=upload)
```

```python
# celery worker (prefork pool)
from celery.signals import worker_process_init

@worker_process_init.connect
def _start_coverage(**kwargs):
    coverage_bootstrap.start(upload=upload)
```

Cron jobs and plain workers call `start()` at the top of `main()`.

Why not `COVERAGE_PROCESS_START` plus a `.pth` file, the documented
subprocess recipe (https://coverage.readthedocs.io/en/latest/subprocess.html):
the `.pth` runs in the master process of uwsgi and gunicorn, before the fork.
Children inherit the tracer, but on Python 2.7 nothing runs in the child to
reset the data file and the save handlers (no `os.register_at_fork`, the hook
modern code uses for that), uwsgi workers exit through C code and do not
reliably run Python `atexit` handlers (uwsgi exposes `uwsgi.atexit` for this
reason), and `os._exit` paths skip `atexit` entirely. The master then holds
most of the bookkeeping and the workers' data is lost or attributed to the
wrong process. Starting in the child, with its own timer and signal handlers,
is the portable rule.

`concurrency`: `"thread"` for threaded workers, `"gevent"` or `"eventlet"` for
monkeypatched workers, `"multiprocessing"` only when the service itself forks
after `start()`.

### 2. Persistence: atexit, SIGTERM, periodic timer, upload

Pods die without notice: eviction, OOM kill, rollout. `coverage_bootstrap`
saves on three triggers, and calls the `upload` hook after each save:

| Trigger | Why |
|---|---|
| `atexit` | normal exit of cron jobs and workers |
| `SIGTERM` (and `uwsgi.atexit` when present) | Kubernetes sends SIGTERM, then SIGKILL after `terminationGracePeriodSeconds` |
| periodic timer, default 300 s | SIGKILL, OOM and node loss never run handlers |

Each save rewrites the same data file (`data_suffix=True` fixes the name at
startup: `.coverage.<host>.pid<pid>.<random>`), so repeated uploads overwrite
one object per process. coverage 7.x renames the file once on the first save
to append a content hash; read `recorder.data_file` after a save rather than
caching it.

Key the bucket path by service and pod:
`coverage/<service>/<pod>/<data file name>`. Keep the source checkout at the
same absolute path in every image (`/app/src/mypkg` everywhere). Then
`coverage combine` needs no `[paths]` remapping and the JSON report keys match
the source tree the analysis job scans.

Use an `emptyDir` or a writable path for `DEADCODE_COVERAGE_DATA_FILE`; a
read-only root filesystem fails the first save.

### 3. Sampling: one replica per Deployment, every CronJob

| Workload | Sample | Reason |
|---|---|---|
| API Deployment | 1 replica of N (a second Deployment with `DEADCODE_COVERAGE=1` and 1 replica, or a pod label plus env) | traffic is load balanced, one replica sees every route over the window |
| Worker Deployments | 1 replica each | same |
| CronJobs | 100% | short-lived, no steady state; every run is one data file |

Process level only. Do not sample requests or tasks inside a process: the
tracer is either on or off for the process, and a process with the tracer on
sees everything it executes.

Overhead is paid by the sampled replica only. With the C tracer it is roughly
1.3x to 2x CPU on web workloads [unverified]; size the sampled replica's
requests and limits for it.

### 4. Combination: daily job, combine, json, zero-hit analysis

```bash
# download everything the window produced
gsutil -m rsync -r gs://bucket/coverage data/

# one combined file per service, then one union
for svc in data/*/; do
    name=$(basename "$svc")
    COVERAGE_FILE="combined/.coverage.$name" coverage combine --keep "$svc"/*/.coverage.*
    COVERAGE_FILE="combined/.coverage.$name" coverage json -o "json/$name.json"
done
COVERAGE_FILE=combined/.coverage.union coverage combine --keep combined/.coverage.*
COVERAGE_FILE=combined/.coverage.union coverage json -o json/union.json
COVERAGE_FILE=combined/.coverage.union coverage report --show-missing --skip-empty
```

`--keep` leaves the inputs in place so the job is rerunnable. On coverage 5.5
`--data-file` does not exist on the command line; `COVERAGE_FILE` works on
every version.

Then the function-level view:

```bash
python scripts/zero_hit_functions.py --source /app/src/mypkg \
    $(for f in json/*.json; do echo --coverage-json "$(basename "$f" .json)=$f"; done) \
    --per-service > zero_hit.txt
```

The script maps executed lines to `def` and `class` ranges with `ast`, so it
works on coverage 5.5 JSON, which has no per-function regions. It prints the
functions and classes with zero executed body lines across **all** services,
and with `--per-service` the services that did hit each function. A module
absent from every service's data is reported as `[module never loaded]`. Run
the script with the interpreter that parses the source (Python 2.7 for a
Python 2 code base); the JSON files can come from any coverage version.

The combined `coverage json` lists files at 0% as well, which is the input for
category 4 (whole modules).

### 5. Window and seasonality

- **Minimum window: 30 days** of continuous collection before any conclusion.
  90 days for worker code. 12 months, or a calendar audit, for anything a job
  touches.
- **Cross with `schedule:` fields.** Export every CronJob's schedule
  (`kubectl get cronjobs -A -o custom-columns=NAME:.metadata.name,SCHEDULE:.spec.schedule,LAST:.status.lastScheduleTime`)
  and beat entries. A job that has not run inside the window leaves its code
  **unknown, not dead**. List those jobs with their next run date in the report.
- **Cross routes with access logs.** Coverage shows what one sampled replica
  executed; access logs show every request. A route with log hits and 0%
  coverage means the sample missed it or the data is incomplete. Trust the logs.
- **Flags that are off** leave their code unexecuted for the whole window. List
  the flags and their state in the report.
- Restart the window after any change to sampling, source paths or the image
  layout.

### 6. Output: candidate list with attached proof

The daily job writes one line per candidate, in the form that becomes the
commit message:

```
mypkg/billing/legacy_export.py  module  0 executed lines
  services: api, worker-billing, worker-notify, cron-monthly-close (+86 more)
  window: 2026-07-01..2026-10-01
  cron jobs not run in window: cron-yearly-archive (next 2027-01-01)
  access log hits for /v1/legacy/export: 0 (2025-10-01..2026-10-01)
```

```
mypkg/billing/invoice.py:214  function Invoice._legacy_total  0 executed lines
  hit by: -
  services: all 141
  window: 2026-07-01..2026-10-01
```

A candidate whose "cron jobs not run in window" line is non-empty, or whose
module is behind an off flag, is not ready. It waits for the next window or a
calendar audit. Everything else moves to the proof ladder in `SKILL.md`,
categories 4 and 5, with this block pasted into the commit message.
