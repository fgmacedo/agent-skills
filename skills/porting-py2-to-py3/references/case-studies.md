# Case studies: tactics that worked at scale

Each entry lists the tactics worth copying and the source. Durations are calendar, not effort.

## Instagram (PyCon 2017 keynote, Lisa Guo and Hui Ding)

- Everything on `master`, no branch. Small commits, never a big merge.
- Phases: third-party packages (3 to 4 months), codemods (2 to 3), unit tests (2), production rollout (4). About 10 months.
- Rule from day one: "No Python 3, no new package."
- Sources: https://www.youtube.com/watch?v=66XoCk79kjM, https://thenewstack.io/instagram-makes-smooth-move-python-3/

## Dropbox (2018 to 2019, desktop client, >1M LOC)

- Straddled both versions in one tree. A runtime switch chose the interpreter, gated by a feature flag, rolled out internal, then beta, then stable. About 7 months of soak.
- py3 unit tests started as module-level skips, un-skipped one file at a time (a ratchet).
- mypy coverage went from 35% to 63% during the port and caught bytes/str mistakes; a per-file blocklist was worked down.
- Commit-queue checks blocked py3 regressions.
- Avoided a global `unicode_literals`.
- Top bug class after cutover: `str(bytes)` producing `"b'...'"`.
- Sources: https://dropbox.tech/application/incrementally-migrating-over-one-million-lines-of-code-from-python-2-to-python-3, https://dropbox.tech/application/how-we-rolled-out-one-of-the-largest-python-3-migrations-ever

## Yelp (3.8M LOC, PyCon 2022, Talk Python #401)

- Milestones in order: parseability (about 2 weeks), importability (1 to 2 months), functional parity (about a year of fixing test failures), rollout (about 2 months). About 1.5 years.
- Separate py2 and py3 environments; one requirements file with environment markers so backports (`futures`, `functools32`) install only on py2.
- Tools: pyupgrade early where possible, python-modernize, six.
- Pickles in memcache moved to JSON over about 3 months with rewrite-on-read.
- An OpenResty proxy routed traffic per endpoint by percentage to py2 or py3 deployments; rollback was moving traffic.
- Result: 15 to 20% faster, about 20% less memory.
- Sources: https://talkpython.fm/episodes/show/401/migrating-3.8-million-lines-of-python, https://www.classcentral.com/classroom/youtube-talk-benjamin-bariteau-how-we-migrated-3-8-million-lines-of-python-2-without-interrupting-deve-244907

## Mercurial (Gregory Szorc, 2020)

- Single source, no flag day. Dropping Python 2.6 first "significantly reduced" the complexity.
- An import-time source transformer added `b''` prefixes; a `pycompat` module served as an in-house `six`.
- `contrib/python3-whitelist`: an allowlist of tests passing on py3, enforced in CI. The ratchet pattern.
- Ran `black` before the big mechanical rewrite and marked those commits `# skip-blame`.
- Lesson stated by the author: "Enforce no-regression policy early."
- Source: https://gregoryszorc.com/blog/2020/01/13/mercurial's-journey-to-and-reflections-on-python-3/

## Python 3.8 porting HOWTO (the last full version of the official guide)

Order: support 2.7 only; get test coverage above 80%; learn the differences; run `futurize` or `modernize`, on the tests first; guard against regressions (`pylint --py3k` then, `python -3 -Werror`); check dependencies; run tox on both versions with `-bb` on py3; optionally run mypy once per version. Bytes/text advice: decode early, encode late, never design APIs that accept both. Use feature detection, not version checks. `//` must be chosen by hand; the tools will not change `/`.
Source: https://docs.python.org/3.8/howto/pyporting.html

## Conservative Python 3 Porting Guide (Red Hat / Fedora)

Order: port dependencies, run the tests, drop Python <= 2.5, port the code, drop Python 2. Chapters map one to one onto the catalog categories (syntax, exceptions, importing, stdlib reorganization, numbers, strings, dictionaries, iterators, builtins, comparing and sorting, classes).
Source: https://portingguide.readthedocs.io/en/latest/

## What the cases have in common

1. No long-lived branch. The port lands on the main branch as py2-compatible commits; the interpreter switch is the only step that needs a branch, and it lives for days.
2. A ratchet in CI from the first week: allowlist or quarantine of py3 failures, strict so that progress cannot slide back.
3. Dependencies before code. The package work is the calendar risk, because it depends on other people.
4. Rollout by traffic or by workload, with rollback that is a routing or image change, never a data migration.
5. Shared serialized state (pickles in caches and queues) handled by namespacing or by switching to a cross-version format before the cutover.
6. A regression gate that stops teammates from reintroducing Python 2 idioms while the port is in flight.
