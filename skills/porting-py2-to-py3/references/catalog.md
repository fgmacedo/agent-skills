# Catalog: what changes from Python 2.7 to 3.x

Each row is classified:

- **M** (mechanical): a tool rewrites it (`futurize --stage1`, `modernize`, `pyupgrade`, ruff `UP`) or a regex finds every site and the fix is the same everywhere.
- **J** (judgment): the agent decides per site with the procedure in the "Decide" column. The decision needs context (who produces the value, who consumes it), not a human. Escalate only the cases listed in `SKILL.md` under "Escalate".

Sources: https://docs.python.org/3/whatsnew/3.0.html, the "Removed" sections of each https://docs.python.org/3/whatsnew/3.X.html, https://portingguide.readthedocs.io/, https://python-future.org/compatible_idioms.html, PEPs named inline.

## A. Syntax (fails to parse on 3.x)

| py2 | py3 | Class | Notes |
|---|---|---|---|
| `print x, y` / `print >>f, x` | `print(x, y)` / `print(x, file=f)` | M | `fix_print_with_import`. Trailing comma becomes `end=' '` |
| `except X, e:` | `except X as e:` | M | On 3.14 the old form parses again as `except (X, e):` (PEP 758) and fails only at runtime. Gate with ruff or a 3.13 interpreter |
| `raise E, "msg"` / `raise E, V, tb` | `raise E("msg")` / `six.reraise(E, V, tb)` or `raise E(V).with_traceback(tb)` | M | |
| `` `x` `` | `repr(x)` | M | |
| `a <> b` | `a != b` | M | |
| `exec code in ns` | `exec(code, ns)` | M/J | On py3 `exec` cannot create locals in a function. If code relied on that, restructure |
| `0777` | `0o777` | M | |
| `10L` | `10` | M | |
| `ur'...'` | `r'...'` with `from __future__ import unicode_literals` in that module, or `u'...'` with doubled backslashes | J | Regex-heavy modules: add `unicode_literals` to those modules only, audit the module for native-str needs first (`struct`, `__slots__`, WSGI, ctypes) |
| `def f(a, (b, c)):` / `lambda (k, v): ...` | unpack in the body | M | `fix_tuple_params` |
| Mixed tabs/spaces | spaces | M | `python2 -tt`, `reindent` |
| `async`, `await`, `nonlocal` as identifiers | rename | M | reserved since 3.7 |
| `"\d"` in a non-raw string | `r"\d"` | M | `DeprecationWarning` 3.6, `SyntaxWarning` 3.12, error later. ruff `W605` |

`from __future__ import ...`: `print_function`, `division`, `absolute_import` are safe to add everywhere and `futurize --stage1` adds them. `unicode_literals` is not safe to add everywhere: it changes the type of every bare literal in the module on 2.7, which breaks `__slots__`, `struct.pack` formats, `type()` names, C-API keyword arguments, WSGI status/headers, `csv` on 2.7, and `os.environ` values. Use explicit `u''` (valid since 3.3) and `b''`, and reserve `unicode_literals` for regex modules. `generator_stop` and `annotations` are py3-only concerns.

## B. Text model (the real cost; almost all J)

| Area | py2 | py3 | Class | Decide |
|---|---|---|---|---|
| Core types | `str` is bytes, `unicode` is text, implicit ASCII coercion | `str` is text, `bytes` is binary, no coercion | J | Unicode sandwich: decode at the input edge, text inside, encode at the output edge. Fix at the edge where the value enters or leaves the process, not where the `TypeError` fires |
| `open()` | bytes | text mode decodes with the locale unless `encoding=` is given; binary needs `'rb'` | J | Every `open()` gets either `encoding='utf-8'` or `'rb'`/`'wb'`. `-X warn_default_encoding` lists the gaps. 3.15 makes UTF-8 the default (PEP 686) |
| stdio | bytes | text; `sys.stdout.buffer` for bytes; `PYTHONIOENCODING`, `PYTHONUTF8=1` | J | Set `LANG`/`PYTHONUTF8=1` in images; use `.buffer` for binary output |
| Indexing bytes | `b'A'[0] == 'A'` | `b'A'[0] == 65`; `bytes([65]) == b'A'` | J | Parser/protocol code: slice (`b[i:i+1]`) instead of index |
| Formatting | `%` works on both | `%` on bytes since 3.5; `'{}'.format(b'x')` and `str(b'x')` give `"b'x'"` | J | **The classic silent bug**: `b'...'` leaking into URLs, SQL, cache keys and logs. Grep `str(` near `.encode`/`b64`/`hashlib`/`subprocess`; add `-bb` so comparisons fail loudly |
| `.decode` / `.encode` | both types have both | only `bytes.decode` and `str.encode` | J | Look at the producer: if it is already text, drop the `.decode`; if bytes, drop the `.encode` |
| `hashlib`, `hmac`, `base64`, `binascii`, `struct`, `zlib`, `socket`, `ssl` | accept `str` | require bytes; `b64encode()` returns bytes | J | `hashlib.md5(s.encode('utf-8'))`; `b64encode(x).decode('ascii')` when the result goes into text. Write a golden test for any hash, token or ID that is persisted or shared |
| `subprocess` | output is `str` | bytes unless `text=True` (3.7) / `encoding=` | J | Add `text=True` when the output is parsed as text |
| `urllib.parse.quote` | bytes in | accepts `str` (encodes UTF-8) or bytes | J | Remove manual pre-encoding to avoid double encoding |
| `json` | returns `unicode` | returns `str`; `loads(bytes)` allowed since 3.6 | M | |
| `csv` | binary files | text mode with `newline=''` | M | `_csv.Error: iterator should return strings` |
| `email` | `email.MIMEText`, str | `email.mime.text`, `message_from_bytes`, `email.policy` | M/J | |
| `pickle` | py2 pickles | `pickle.load(f, encoding='latin1')` reads py2 `str`/`datetime` data; py3 default protocol 4/5 is unreadable by py2 | J | Shared caches and queues during a mixed rollout: namespace keys per interpreter (`py3:` prefix) or flush at cutover; pin `protocol=2` while both run. Escalate: persisted format |
| `shelve`, `marshal`, `dbm` | | backends and formats differ | J | Regenerate; do not migrate |
| WSGI (PEP 3333) | | environ values are native `str` decoded as latin-1; body and `wsgi.input` are bytes; status and headers are native `str` | J | Werkzeug handles the latin-1 round trip; custom middleware must not |
| Flask / Werkzeug | | `request.data` is bytes; `request.get_data(as_text=True)` for text; `Response` accepts both | J | |
| Jinja2 / MarkupSafe | `Markup` subclasses `unicode` | `Markup` subclasses `str`; bytes render as `b'..'` | J | |
| SQLAlchemy | `String` could return bytes; `convert_unicode` | `String` is `str`, `LargeBinary` is bytes; `convert_unicode` removed in 2.0 | J | Columns holding binary data must be `LargeBinary` |
| MySQL driver | `use_unicode=False` default in MySQLdb | mysqlclient/PyMySQL return `str`; set `charset='utf8mb4'` | J | |
| Redis | returns `str` (bytes) | returns bytes unless `decode_responses=True` | J | `== 'value'` comparisons silently false; `-bb` finds them |
| ctypes | `c_char_p` accepts `str` | `c_char_p` needs bytes; `c_wchar_p` for text | J | Encode at the FFI boundary once |
| `os.environ`, `os.listdir`, paths | bytes | `str`; `os.environb`, `os.listdir(b'.')` for bytes; surrogateescape for undecodable names | J | |

## C. Numbers and ordering

| py2 | py3 | Class | Decide |
|---|---|---|---|
| `7 / 2 == 3` | `3.5`; `//` for floor | J | `python2 -Qwarnall` lists every int `/`. Use `//` when both operands are integers by construction (indices, pagination, counts, chunk sizes); otherwise keep `/` and add `from __future__ import division` so py2 behaves like py3 in the window |
| `int` / `long` | `int` only | M | `isinstance(x, six.integer_types)` |
| `sys.maxint` | `sys.maxsize` (same value on 64-bit CPython) | M | Golden test for anything derived from it |
| `round(2.5) == 3.0` | `2` (banker's rounding, returns `int`) | J | Money and reports: `decimal.Decimal.quantize(..., ROUND_HALF_UP)`. Escalate if visible to customers |
| `None < 1`, `[] < ''`, `{} < []` | `TypeError` | J | `sorted(rows, key=lambda r: (r.x is None, r.x))`; normalize types before comparing |
| `cmp()`, `sorted(cmp=)`, `list.sort(cmp)`, `__cmp__` | `functools.cmp_to_key`, rich comparisons, `functools.total_ordering` | M/J | `python2 -3` warns on each |
| `hash(str)` differs per process on 3.x (PYTHONHASHSEED) | | J | Anything persisted from `hash()` must use `hashlib` instead |
| `random` with a fixed seed | `randrange`/`randint`/`choice`/`shuffle`/`sample` changed in 3.2; `seed(str)` hashing changed | J | Fixtures and tests that depend on seeded sequences need regenerated expectations; `random.seed(x, version=1)` does not restore the old sequence |
| `oct(8) == '010'`, `hex(10L) == '0xaL'` | `'0o10'`, `'0xa'` | J | Only if the output is parsed |

## D. Special methods and classes

| py2 | py3 | Class | Notes |
|---|---|---|---|
| `__nonzero__` | `__bool__` | M | Otherwise the object is always truthy, silently |
| `__div__`, `__idiv__`, `__rdiv__` | `__truediv__` family | M | |
| `__unicode__` returning text, `__str__` returning bytes | `__str__` returns text | M | Define `__str__`; keep `__unicode__ = __str__` during the window if py2 callers use it |
| `__cmp__` | rich comparisons | J | |
| `__getslice__`/`__setslice__`/`__delslice__` | `__getitem__` with `slice` | J | |
| `__eq__` without `__hash__` | `__hash__` becomes `None` | J | `TypeError: unhashable type` in sets and dict keys; add `__hash__` or decide the class is unhashable |
| `__metaclass__ = M` | `class C(metaclass=M)`, `six.add_metaclass(M)` | M | Silently ignored on py3 otherwise: registries and ORM hooks never fire |
| `.next()` | `__next__` and `next(it)` | M | |
| Old-style classes (`class A:` without `object`) | all classes are new-style | J | `__getattr__` no longer intercepts special methods; MRO is C3; `type(inst)` is the class |
| `im_func`/`im_self`/`im_class`, `func_name`/`func_code`/`func_defaults`/`func_closure`/`func_globals` | `__func__`/`__self__`, `__name__`/`__code__`/`__defaults__`/`__closure__`/`__globals__` | M | |
| Unbound methods | plain functions | J | `C.method.im_class` has no equivalent |

## E. Iterators, views, builtins

| py2 | py3 | Class | Decide |
|---|---|---|---|
| `d.keys()`, `d.values()`, `d.items()` return lists | views | J | `d.keys()[0]` becomes `next(iter(d))`; `.sort()` on them becomes `sorted(...)`; deleting while iterating raises `RuntimeError: dictionary changed size during iteration`, so iterate over `list(d)` |
| `iteritems`/`iterkeys`/`itervalues`/`view*` | `items()` etc. or `six.iteritems` | M | |
| `d.has_key(k)` | `k in d` | M | |
| `map`, `filter`, `zip` return lists | lazy iterators | J | Wrapping in `list()` is only needed when the result is indexed, measured with `len()`, or iterated twice. A second iteration of an exhausted iterator is **silently empty**. `map(None, ...)` is gone |
| `range` list / `xrange` | `range` (lazy, sliceable) | M | |
| `reduce`, `intern`, `reload`, `apply`, `execfile`, `file()`, `buffer`, `unichr`, `unicode`, `basestring`, `long`, `cmp`, `raw_input`, `coerce` | `functools.reduce`, `sys.intern`, `importlib.reload`, `f(*a)`, `exec(open(f).read())`, `open()`, `memoryview`, `chr`, `str`, `str`, `int`, rich comparisons, `input`, gone | M | `six.string_types`, `six.text_type`, `six.integer_types` during the window |
| `input()` evaluates its input | `input()` returns `str` | M | `six.moves.input` |
| `string.letters`/`lowercase`/`uppercase`, `string.maketrans`, `string.join` and friends | `string.ascii_*`, `str.maketrans`/`bytes.maketrans`, `str` methods | M | |
| `str.translate(table, deletechars)` | `str.translate(dict)`; `bytes.translate(table, delete)` | J | |
| `os.getcwdu()` | `os.getcwd()` | M | |
| `e.message` | `str(e)` or `e.args[0]` | M | |
| `sys.exc_type`/`exc_value`/`exc_traceback`, `sys.exc_clear()` | `sys.exc_info()` | M | |
| `itertools.izip`/`imap`/`ifilter`/`ifilterfalse`/`izip_longest` | `zip`/`map`/`filter`/`filterfalse`/`zip_longest` | M | |
| `operator.div`/`idiv`/`sequenceIncludes`/`isCallable` | `truediv`/`floordiv`, `contains`, `callable()` | M | |
| `types.StringType` and friends | builtins | M | |

## F. Module renames (PEP 3108), all M via `six.moves` or the new name

- `urllib2`, `urllib`, `urlparse` become `urllib.request`, `urllib.parse`, `urllib.error`; `robotparser` becomes `urllib.robotparser`.
- `httplib` becomes `http.client`; `BaseHTTPServer`/`SimpleHTTPServer`/`CGIHTTPServer` become `http.server`; `Cookie` becomes `http.cookies`; `cookielib` becomes `http.cookiejar`; `HTMLParser` becomes `html.parser`; `htmlentitydefs` becomes `html.entities`; `xmlrpclib` becomes `xmlrpc.client`; `SimpleXMLRPCServer`/`DocXMLRPCServer` become `xmlrpc.server`.
- `StringIO`/`cStringIO` become `io.StringIO` (text) or `io.BytesIO` (binary): this one is J, choose by content. `cPickle` becomes `pickle`.
- `ConfigParser`, `Queue`, `SocketServer`, `Tkinter` are lower-cased; `__builtin__` becomes `builtins`; `copy_reg` becomes `copyreg`; `repr` becomes `reprlib`; `thread` becomes `_thread`.
- `anydbm`/`whichdb`/`dbm`/`gdbm`/`dumbdbm` become `dbm.*`; `UserDict`/`UserList`/`UserString` move to `collections`.
- Gone with a replacement: `commands` (`subprocess`), `popen2` (`subprocess`), `md5`/`sha` (`hashlib`), `sets` (builtin `set`), `exceptions` (builtins), `new` (`types`), `mimetools`/`rfc822`/`MimeWriter`/`mimify`/`multifile` (`email`), `dircache`, `statvfs` (`os.statvfs`), `compiler` (`ast`), `sgmllib`/`htmllib` (`html.parser`), `imputil`/`ihooks`/`imp` (`importlib`; `imp` removed in 3.12), `mock` (`unittest.mock`).

## G. Imports and packaging

| py2 | py3 | Class | Decide |
|---|---|---|---|
| Implicit relative import (`import utils` inside a package) | `from . import utils` or absolute | M/J | `fix_absolute_import` rewrites; a name collision with a top-level module needs a rename. `scripts/py2ism_census.py` counts them by sibling lookup |
| Missing `__init__.py` raises `ImportError` | directory silently imports as a namespace package (PEP 420) | J | Tests dirs with duplicate basenames and no `__init__.py` produce "import file mismatch" under pytest |
| `from x import *` inside a function | `SyntaxError` | M | |
| `sys.path[0]` | script dir, or `''` for `-c`/`-m`; 3.11 adds `-P`/`PYTHONSAFEPATH` | J | Run entry points with `python -m pkg.mod`; delete `sys.path.append('..')` hacks |
| `pkg_resources` | `importlib.metadata` (3.8), `importlib.resources.files()` (3.9); `pkg_resources` removed in setuptools 82 (2026-02) | M | |
| `distutils` | removed in 3.12; `packaging.version`, `shutil.which`, setuptools | M | |
| `setup.py install`, `easy_install` | gone (setuptools 80) | M | |

## H. Exceptions

| py2 | py3 | Class | Notes |
|---|---|---|---|
| `StandardError` | `Exception` | M | |
| `IOError`, `EnvironmentError`, `WindowsError`, `socket.error`, `select.error` | all aliases of `OSError` (PEP 3151); `FileNotFoundError`, `ConnectionResetError`, `TimeoutError` replace `errno` checks | M/J | |
| `except` variable survives the block | deleted at the end of the `except` block | J | `UnboundLocalError` later; rebind to another name |
| `StopIteration` inside a generator | `RuntimeError` (PEP 479, default since 3.7) | J | `return` instead of `raise StopIteration`; guard `next()` inside generators |
| No chaining | `__context__`/`__cause__`, `raise X from Y` | M | Tracebacks grow a "During handling of the above exception" section |
| `str(KeyError('x')) == 'x'` | `"'x'"` | J | Tests asserting on messages |

## I. Strings, repr and test snapshots (J)

- `repr(u'x')` is `u'x'` on py2 and `'x'` on py3; `repr(b'x')` is `b'x'`; no `L` suffix. Doctests, snapshot tests and anything that logs or caches a `repr` change.
- Dict order is insertion order since 3.7; set order and `hash(str)` vary per process since 3.3. Tests that depend on either need sorting or `PYTHONHASHSEED` pinned in the test runner only.
- `re` on `str` patterns: `\d`, `\w`, `\s`, `\b` are Unicode-aware. `\d` matches non-ASCII digits, which is a validation and security concern. Use `re.ASCII` or `[0-9]` where ASCII was assumed. Bytes patterns need bytes input.
- `str.isdigit`/`isnumeric`/`isdecimal` and `str.split()` follow Unicode; `'ß'.upper() == 'SS'`; `casefold()` exists.
- `sorted()`/`max()` over heterogeneous keys raise.
- `datetime.utcnow()` deprecated in 3.12 (`datetime.now(timezone.utc)`); naive/aware comparisons raise.

## J. Stdlib behaviour by version (M via ruff `UP`, grep, or `-W error`)

- 3.8: `time.clock` (`perf_counter`), `cgi.escape` (`html.escape`), `cgi.parse_qs` (`urllib.parse.parse_qs`), `platform.linux_distribution` (`distro` on PyPI).
- 3.9: `base64.encodestring`/`decodestring` (`encodebytes`/`decodebytes`), `array.tostring` (`tobytes`), `ElementTree.getchildren`/`getiterator`, `Thread.isAlive` (`is_alive`), `json.loads(encoding=)`, `fractions.gcd` (`math.gcd`).
- 3.10: `collections.Mapping` and the other ABC aliases (`collections.abc`), asyncio `loop=` parameters, `parser` and `formatter` modules.
- 3.11: `inspect.getargspec` (`signature`), `asyncio.coroutine`, `binhex`, `gettext.lgettext`.
- 3.12: `distutils`, `imp`, `asynchat`/`asyncore`/`smtpd`, unittest aliases (`assertEquals`, `assertNotEquals`, `assertAlmostEquals`, `assertRaisesRegexp`, `assertRegexpMatches`, `assert_`, `failUnless`, `failIf`, `assertDictContainsSubset`), `assertItemsEqual` (`assertCountEqual`, gone since 3.2), `configparser.SafeConfigParser`/`readfp`, `ssl.wrap_socket`/`match_hostname`, `locale.format`, `random.randrange(10.0)`, invalid escapes become `SyntaxWarning`, venvs without setuptools.
- 3.13: PEP 594 modules `aifc`, `audioop`, `cgi`, `cgitb`, `chunk`, `crypt`, `imghdr`, `mailcap`, `msilib`, `nis`, `nntplib`, `ossaudiodev`, `pipes`, `sndhdr`, `spwd`, `sunau`, `telnetlib`, `uu`, `xdrlib` (`cgi.FieldStorage` to `multipart`/`email`; `pipes.quote` to `shlex.quote`; `crypt` to `bcrypt`/`passlib`; `imghdr` to `filetype`/Pillow); `lib2to3`; `locale.resetlocale`; `typing.io`/`typing.re`; `unittest.makeSuite`/`findTestCases`.
- 3.14: `ast.Num`/`Str`/`Bytes`/`NameConstant`; `pkgutil.find_loader`/`get_loader`; `asyncio.get_event_loop()` raises with no running loop; `urllib.request.URLopener`; `sqlite3.version`. Behaviour: `multiprocessing` and `ProcessPoolExecutor` default to `forkserver` on Linux (targets and args must be picklable; globals mutated at runtime are not inherited; gunicorn and Celery prefork use raw `fork` and are unaffected); `tarfile` default filter is `data`; `functools.partial` is a method descriptor; lazy annotations (PEP 649).
- Pending (run with `-W error::DeprecationWarning`): `datetime.utcnow`, `logging.warn`, `codecs.open`, `shutil.rmtree(onerror=)`, ssl `PROTOCOL_TLS`/`OP_NO_*`, threading camelCase names, `typing.Text`, `collections.abc.ByteString` (3.17), asyncio policy system (3.16).

## K. Concurrency and process model (J)

- `fork` with inherited SQLAlchemy engines: call `engine.dispose(close=False)` in the child, or create engines after the fork. With `spawn`/`forkserver`, never pass engines, sessions or connections to workers.
- `threading.Thread.isAlive` (3.9), `thread.get_ident` (`threading.get_ident`), `Queue` rename.
- eventlet/gevent monkey patching: pin versions that support both interpreters during the window (`eventlet` 0.30.x, `gevent` 22.10.x); verify `ssl` patching on the target, it changed in every 3.x minor.
- `signal`, `select`, `socket` constants are enums; comparisons with ints still work.
