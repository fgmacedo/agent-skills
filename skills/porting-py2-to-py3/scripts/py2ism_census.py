#!/usr/bin/env python3
"""Count Python 2 idioms per category and compare against a saved baseline.

Usage:
    python3 py2ism_census.py SRC_DIR [SRC_DIR...]             # print the census
    python3 py2ism_census.py SRC_DIR --save baseline.json     # record a baseline
    python3 py2ism_census.py SRC_DIR --check baseline.json    # exit 1 if any category grew

The census is regex-based so it runs on any interpreter and on code that does
not parse as Python 3 yet. Counts are occurrences, not proofs: a category at
zero means the idiom is gone, a non-zero count is a worklist.
"""
from __future__ import print_function

import argparse
import io
import json
import os
import re
import sys

# category -> (regex, hint). Order matters only for display.
PATTERNS = [
    # syntax that fails to parse on Python 3
    ("print_statement", r"^\s*print\s+(?!\(|\s*$)[^=(]", "print(...) with print_function"),
    ("except_comma", r"^\s*except\s+[\w.]+(\s*,\s*[\w.]+)*\s*,\s*\w+\s*:", "except X as e"),
    ("raise_comma", r"^\s*raise\s+[\w.]+\s*,", "raise X(msg)"),
    ("backticks", r"`[^`\n]+`", "repr(x)"),
    ("ne_diamond", r"(?<![<>=!'\"])\s<>\s(?!['\"])", "!="),
    ("exec_statement", r"^\s*exec\s+[^(]", "exec(code, ns)"),
    ("octal_literal", r"(?<![\w.])0[0-7]+\b(?!\.)", "0o755"),
    ("long_literal", r"\b\d+[lL]\b", "drop the L suffix"),
    ("ur_string", r"\b[uU][rR]['\"]", "r'' under unicode_literals, or u'\\\\d'"),
    ("tuple_param_unpack", r"^\s*(def\s+\w+|lambda)\s*\([^)]*\([^)]*\)", "unpack inside the body"),
    # builtins and names removed in Python 3
    ("basestring", r"\bbasestring\b", "six.string_types or str"),
    ("unicode_call", r"\bunicode\(", "six.text_type or str"),
    ("long_call", r"\blong\(", "int"),
    ("xrange", r"\bxrange\(", "range"),
    ("raw_input", r"\braw_input\(", "input"),
    ("unichr", r"\bunichr\(", "chr"),
    ("reduce_builtin", r"(?<![\w.])reduce\(", "functools.reduce"),
    ("apply_builtin", r"(?<![\w.])apply\(", "f(*args, **kw)"),
    ("execfile", r"\bexecfile\(", "exec(open(f).read())"),
    ("file_builtin", r"(?<![\w.])file\(", "open()"),
    ("buffer_builtin", r"(?<![\w.])buffer\(", "memoryview"),
    ("cmp_builtin", r"(?<![\w.])cmp\(", "rich comparisons"),
    ("sys_maxint", r"\bsys\.maxint\b", "sys.maxsize"),
    ("exception_message", r"\b(e|ex|exc|err|error|exception)\.message\b", "str(e) / e.args[0]"),
    ("string_letters", r"\bstring\.(letters|lowercase|uppercase)\b", "string.ascii_*"),
    ("string_maketrans", r"\bstring\.maketrans\b", "str.maketrans / bytes.maketrans"),
    ("os_getcwdu", r"\bos\.getcwdu\b", "os.getcwd"),
    # dict and iterator protocol
    ("dict_iter_methods", r"\.(iteritems|iterkeys|itervalues|viewitems|viewkeys|viewvalues)\(", "items()/keys()/values() or six.iteritems"),
    ("dict_has_key", r"\.has_key\(", "key in d"),
    ("dict_view_indexing", r"\.(keys|values|items)\(\)\s*\[", "list(d.keys())[i] or next(iter(d))"),
    ("next_method", r"\.next\(\)", "next(it)"),
    ("sort_cmp", r"\.sort\(\s*cmp\s*=|sorted\([^)]*\bcmp\s*=", "key=functools.cmp_to_key(f)"),
    # special methods
    ("dunder_nonzero", r"\bdef __nonzero__\b", "__bool__"),
    ("dunder_div", r"\bdef __(r|i)?div__\b", "__truediv__"),
    ("dunder_cmp", r"\bdef __cmp__\b", "__eq__/__lt__ + functools.total_ordering"),
    ("dunder_unicode", r"\bdef __unicode__\b", "__str__"),
    ("dunder_getslice", r"\bdef __(get|set|del)slice__\b", "__getitem__ with slice"),
    ("metaclass_attr", r"^\s*__metaclass__\s*=", "six.add_metaclass / metaclass="),
    ("func_attrs", r"\.(func_name|func_defaults|func_code|func_globals|func_closure|func_dict|im_func|im_self|im_class)\b", "__name__, __defaults__, __code__, __func__, __self__"),
    # renamed stdlib modules
    ("py2_stdlib_import", r"^\s*(?:import|from)\s+(urllib2|urlparse|StringIO|cStringIO|cPickle|ConfigParser|Queue|SocketServer|__builtin__|httplib|HTMLParser|htmlentitydefs|Cookie|cookielib|commands|xmlrpclib|BaseHTTPServer|SimpleHTTPServer|CGIHTTPServer|Tkinter|copy_reg|repr|thread|dummy_thread|anydbm|whichdb|dbm|gdbm|dumbdbm|UserDict|UserList|UserString|md5|sha|sets|exceptions|new|popen2|mimetools|rfc822|MimeWriter|mimify|robotparser|imp|sgmllib|htmllib|compiler)\b", "six.moves / new module name"),
    ("urllib_py2_funcs", r"\burllib\.(quote|unquote|urlencode|quote_plus|unquote_plus|urlopen|urlretrieve)\b", "urllib.parse / urllib.request (six.moves.urllib)"),
    ("itertools_i_funcs", r"\bitertools\.(izip|imap|ifilter|ifilterfalse|izip_longest)\b", "zip/map/filter/filterfalse/zip_longest"),
    ("types_constants", r"\btypes\.(StringType|StringTypes|UnicodeType|IntType|LongType|ListType|DictType|TupleType|NoneType|BooleanType|FloatType|ClassType|InstanceType)\b", "builtin types / isinstance"),
    ("collections_abc_alias", r"\bcollections\.(Mapping|MutableMapping|Sequence|MutableSequence|Set|MutableSet|Iterable|Iterator|Callable|Container|Sized|Hashable)\b", "collections.abc.X (removed 3.10)"),
    ("os_errno_exceptions", r"\b(StandardError|socket\.error|select\.error|WindowsError)\b", "OSError and subclasses"),
    ("unittest_aliases", r"\.(assertEquals|assertNotEquals|assertAlmostEquals|assertItemsEqual|assertRaisesRegexp|assertRegexpMatches|assert_|failUnless|failIf)\(", "assertEqual/assertCountEqual/assertRaisesRegex (removed 3.12)"),
    # things that still parse but hide a judgment call
    ("future_import", r"^\s*from __future__ import", "informational"),
    ("six_usage", r"\bsix\.", "informational: shim to remove after cutover"),
    ("future_runtime", r"^\s*from (builtins|future|past)\b", "informational: python-future runtime shim"),
    ("coding_header", r"^#.*coding[:=]\s*utf-?8", "informational: drop after cutover"),
    ("u_prefix_literal", r"(?<![\w])[uU](['\"])", "informational: valid on py3, drop after cutover"),
    ("encode_decode_call", r"\.(encode|decode)\(", "informational: bytes/str boundary to audit"),
    ("division_operator", r"(?<![/*=!<>])\s/\s(?!/)", "informational: audit for integer division (python2 -Qwarnall)"),
    ("round_call", r"(?<![\w.])round\(", "informational: banker's rounding on py3"),
    ("sorted_call", r"(?<![\w.])(sorted|max|min)\(", "informational: mixed-type or None ordering"),
    ("hashlib_call", r"\bhashlib\.(md5|sha1|sha256|sha512|new)\(", "informational: needs bytes on py3"),
    ("pickle_usage", r"\b(c?[pP]ickle|marshal|shelve)\b", "informational: persisted data format"),
]

INFORMATIONAL = {name for name, _, hint in PATTERNS if hint.startswith("informational")}
IMPLICIT_RELATIVE = "implicit_relative_import"

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".tox", "build", "dist", ".eggs"}


def iter_py_files(roots):
    for root in roots:
        if os.path.isfile(root):
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(filenames):
                if name.endswith(".py"):
                    yield os.path.join(dirpath, name)


STRING_RX = re.compile(
    r'("""|\'\'\')(?:.|\n)*?\1'
    r'|"(?:\\.|[^"\\\n])*"'
    r"|'(?:\\.|[^'\\\n])*'"
)
IMPORT_RX = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)(?![A-Za-z0-9_])", re.MULTILINE)


def blank_string_contents(text):
    """Keep prefixes and quotes, drop what is inside, so string bodies never match."""
    def repl(m):
        q = m.group(0)
        if q.startswith(('"""', "'''")):
            return q[:3] + q[-3:]
        return q[0] + q[-1]
    return STRING_RX.sub(repl, text)


def sibling_modules(dirpath):
    names = set()
    for entry in os.listdir(dirpath):
        full = os.path.join(dirpath, entry)
        if entry.endswith(".py") and entry != "__init__.py":
            names.add(entry[:-3])
        elif os.path.isdir(full) and os.path.exists(os.path.join(full, "__init__.py")):
            names.add(entry)
    return names


def count_implicit_relative_imports(path, text, cache):
    dirpath = os.path.dirname(path) or "."
    if not os.path.exists(os.path.join(dirpath, "__init__.py")):
        return 0
    if dirpath not in cache:
        cache[dirpath] = sibling_modules(dirpath)
    siblings = cache[dirpath]
    return sum(1 for m in IMPORT_RX.finditer(text) if m.group(1) in siblings)


def strip_comment(line):
    in_quote = None
    for i, ch in enumerate(line):
        if in_quote:
            if ch == in_quote and line[i - 1] != "\\":
                in_quote = None
        elif ch in ("'", '"'):
            in_quote = ch
        elif ch == "#":
            return line[:i]
    return line


def census(roots):
    compiled = [(name, re.compile(rx, re.MULTILINE), hint) for name, rx, hint in PATTERNS]
    counts = {name: {"occurrences": 0, "files": set(), "hint": hint} for name, _, hint in PATTERNS}
    counts[IMPLICIT_RELATIVE] = {"occurrences": 0, "files": set(),
                                 "hint": "from . import x / absolute import (fix_absolute_import)"}
    sibling_cache = {}
    total_files = 0
    for path in iter_py_files(roots):
        total_files += 1
        with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = blank_string_contents("".join(strip_comment(line) for line in fh))
        rel = count_implicit_relative_imports(path, text, sibling_cache)
        if rel:
            counts[IMPLICIT_RELATIVE]["occurrences"] += rel
            counts[IMPLICIT_RELATIVE]["files"].add(path)
        for name, rx, _ in compiled:
            hits = rx.findall(text)
            if hits:
                counts[name]["occurrences"] += len(hits)
                counts[name]["files"].add(path)
    for entry in counts.values():
        entry["files"] = len(entry["files"])
    return {"total_files": total_files, "categories": counts}


def print_report(result, show_info):
    cats = result["categories"]
    print("files scanned: %d" % result["total_files"])
    print("%-32s %10s %6s  %s" % ("category", "occurrences", "files", "hint"))
    for name in [n for n, _, _ in PATTERNS] + [IMPLICIT_RELATIVE]:
        entry = cats[name]
        if name in INFORMATIONAL and not show_info:
            continue
        if entry["occurrences"] == 0:
            continue
        print("%-32s %10d %6d  %s" % (name, entry["occurrences"], entry["files"], entry["hint"]))
    blocking = sum(c["occurrences"] for n, c in cats.items() if n not in INFORMATIONAL)
    print("blocking occurrences (non-informational): %d" % blocking)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("roots", nargs="+")
    parser.add_argument("--save", metavar="BASELINE_JSON")
    parser.add_argument("--check", metavar="BASELINE_JSON")
    parser.add_argument("--json", action="store_true", help="print the census as JSON")
    parser.add_argument("--all", action="store_true", help="include informational categories")
    args = parser.parse_args(argv)

    result = census(args.roots)
    if args.json:
        print(json.dumps(result, indent=1, sort_keys=True))
    else:
        print_report(result, args.all)

    if args.save:
        with open(args.save, "w") as fh:
            json.dump(result, fh, indent=1, sort_keys=True)
        print("baseline saved to %s" % args.save)

    if args.check:
        with open(args.check) as fh:
            baseline = json.load(fh)["categories"]
        regressions = []
        for name, entry in result["categories"].items():
            if name in INFORMATIONAL:
                continue
            before = baseline.get(name, {}).get("occurrences", 0)
            if entry["occurrences"] > before:
                regressions.append((name, before, entry["occurrences"]))
        if regressions:
            print("REGRESSION: py2 idioms increased vs baseline")
            for name, before, after in regressions:
                print("  %-32s %d -> %d" % (name, before, after))
            return 1
        print("ok: no category grew vs baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
