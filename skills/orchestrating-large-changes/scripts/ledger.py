"""Render a run's progress from its plan graph and its ledger.

  python3 ledger.py show CORE LEDGER [--ascii] [--color auto|always|never] [--repo DIR]
  python3 ledger.py times CORE LEDGER
  python3 ledger.py mermaid CORE LEDGER
  python3 ledger.py table CORE LEDGER --link DIR
  python3 ledger.py add LEDGER TEXT... [--tz ZONE]

CORE is the plan's core.md: its first Mermaid flowchart gives the nodes, the edges and the
releases (subgraphs). A node with a file in tasks/ next to CORE (tasks/T7-slug.md or
tasks/T7.md), or with an id like T7, is a task; any other node is a gate. LEDGER lines of the form
"- HH:MM ID[,ID...] EVENT details" set the status; "## YYYY-MM-DD" headings set the day.
EVENT is one of: dispatched, started, reported, clean, fix, merged, passed, held, dropped.
`add` appends "- HH:MM TEXT", now in ZONE (default: local), after a day heading if new.
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

STATUSES = ("todo", "wip", "review", "done", "held", "dropped")
EVENTS = {
    "dispatched": "wip",
    "started": "wip",
    "reported": "review",
    "clean": "review",
    "fix": "wip",
    "merged": "done",
    "passed": "done",
    "held": "held",
    "dropped": "dropped",
}
GLYPH = {"done": "✔", "wip": "◐", "review": "◎", "todo": "·", "held": "⏸", "dropped": "✗"}
ASCII_GLYPH = {"done": "x", "wip": "~", "review": "r", "todo": ".", "held": "h", "dropped": "-"}
WORDS = {
    "done": "merged",
    "wip": "in progress",
    "review": "in review",
    "todo": "not started",
    "held": "held",
    "dropped": "dropped",
}
ANSI = {"done": "32", "wip": "33", "review": "33", "todo": "2", "held": "31", "dropped": "2;9"}
MERMAID_CLASS = {
    "done": "fill:#2e7d32,color:#fff,stroke:#1b5e20",
    "wip": "fill:#f9a825,color:#000,stroke:#f57f17",
    "review": "fill:#f9a825,color:#000,stroke:#f57f17",
    "todo": "fill:#eeeeee,color:#555,stroke:#9e9e9e",
    "held": "fill:#ffffff,color:#b71c1c,stroke:#b71c1c,stroke-dasharray:4 3",
    "dropped": "fill:#ffffff,color:#9e9e9e,stroke:#bdbdbd,stroke-dasharray:2 2",
    "gate": "fill:#1565c0,color:#fff,stroke:#0d47a1",
}

NODE = re.compile(r"^([A-Za-z_][\w-]*)\s*(?:\[\"?(.*?)\"?\]|\(\"?(.*?)\"?\)|\{\"?(.*?)\"?\})?$")
ARROW = re.compile(r"\s*(?:<?-->|<?==>|-\.->|---|--[^-<>|]+-->)\s*")
DAY = re.compile(r"^#+\s+(\d{4}-\d{2}-\d{2})\b")
LINE = re.compile(r"^-\s+(\d{1,2}:\d{2})\s+([A-Za-z_][\w-]*(?:,[A-Za-z_][\w-]*)*)\s+(%s)\b\s*(.*)$" % "|".join(EVENTS))


def plan_graph(text):
    block, inside = [], False
    for line in text.splitlines():
        if not inside and line.strip().startswith("```mermaid"):
            inside, block = True, []
        elif inside and line.strip().startswith("```"):
            if any(re.match(r"\s*(flowchart|graph)\b", b) for b in block):
                break
            inside = False
        elif inside:
            block.append(line)
    nodes, edges, release = {}, [], None
    for raw in block:
        line = re.sub(r"%%.*", "", raw).strip()
        if not line or re.match(r"(flowchart|graph|classDef|class|style|linkStyle|direction)\b", line):
            continue
        if line.startswith("subgraph"):
            m = re.match(r"subgraph\s+([\w-]+)\s*(?:\[\"?(.*?)\"?\])?", line)
            release = (m.group(2) or m.group(1)) if m else None
            continue
        if line == "end":
            release = None
            continue
        line = re.sub(r"\|[^|]*\|", "", line)
        groups = []
        for segment in ARROW.split(line):
            ids = []
            for token in segment.split("&"):
                nm = NODE.match(token.strip())
                if not nm:
                    continue
                node_id = nm.group(1)
                label = next((g for g in nm.groups()[1:] if g), None)
                node = nodes.setdefault(node_id, {"label": node_id, "release": release})
                if label:
                    node["label"] = label
                if release and not node["release"]:
                    node["release"] = release
                ids.append(node_id)
            groups.append(ids)
        for left, right in zip(groups, groups[1:]):
            edges += [(a, b) for a in left for b in right]
    return nodes, edges


def task_files(core):
    folder = os.path.join(os.path.dirname(os.path.abspath(core)), "tasks")
    found = {}
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.endswith(".md"):
                found[re.split(r"[-.]", name, maxsplit=1)[0]] = os.path.join(folder, name)
    return found


def core_title(core):
    with open(core, encoding="utf-8") as f:
        for line in f:
            if line.startswith("# "):
                return line[2:].strip()
    return os.path.basename(os.path.dirname(os.path.abspath(core)))


def task_title(path, task_id):
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"#\s+(.+)", line)
            if m:
                return re.sub(rf"^{re.escape(task_id)}\b[\s:.-]*", "", m.group(1).strip())
    return task_id


def load(core, ledger):
    with open(core, encoding="utf-8") as f:
        nodes, edges = plan_graph(f.read())
    files = task_files(core)
    for task_id in files:
        nodes.setdefault(task_id, {"label": task_id, "release": None})
    items = {}
    for order, (node_id, node) in enumerate(nodes.items()):
        path = files.get(node_id)
        items[node_id] = {
            "id": node_id,
            "title": task_title(path, node_id) if path else node["label"],
            "file": os.path.basename(path) if path else None,
            "kind": "task" if path or re.fullmatch(r"T\d+", node_id) else "gate",
            "release": node["release"],
            "deps": sorted({a for a, b in edges if b == node_id}),
            "order": order,
            "status": "todo",
            "note": "",
            "start": None,
            "end": None,
            "fixes": 0,
        }
    day, last, updated = None, None, None
    with open(ledger, encoding="utf-8") as f:
        for line in f:
            dm = DAY.match(line)
            if dm:
                day = datetime.date.fromisoformat(dm.group(1))
                last = None
                continue
            m = LINE.match(line.strip())
            if not m:
                continue
            clock, ids, event, details = m.groups()
            hour, minute = map(int, clock.split(":"))
            base = day or datetime.date(2000, 1, 1)
            when = datetime.datetime.combine(base, datetime.time(hour, minute))
            while last and when < last:
                when += datetime.timedelta(days=1)
            last = updated = when
            for item_id in ids.split(","):
                item = items.get(item_id)
                if not item:
                    continue
                item["status"] = EVENTS[event]
                if event in ("dispatched", "started") and not item["start"]:
                    item["start"] = when
                if event in ("merged", "passed"):
                    item["end"] = when
                if event == "fix":
                    item["fixes"] += 1
                if event in ("held", "dropped"):
                    item["note"] = details.lstrip("-: ").strip()
                else:
                    item["note"] = ""
    return list(items.values()), updated, day is not None


def levels(items):
    index = {i["id"]: i for i in items}
    memo = {}

    def level(item_id, trail=()):
        if item_id in memo:
            return memo[item_id]
        if item_id in trail:
            return 0
        deps = [d for d in index[item_id]["deps"] if d in index]
        memo[item_id] = 1 + max((level(d, trail + (item_id,)) for d in deps), default=0)
        return memo[item_id]

    return {i["id"]: level(i["id"]) for i in items}


def bar(done, total, width, ascii_only):
    filled = round(width * done / total) if total else width
    full, empty = ("#", "-") if ascii_only else ("█", "░")
    return f"[{full * filled}{empty * (width - filled)}]"


def head(repo):
    try:
        return subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def cmd_show(args):
    all_items, updated, dated = load(args.core, args.ledger)
    color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty() and not os.environ.get("NO_COLOR"))
    glyphs = ASCII_GLYPH if args.ascii else GLYPH

    def paint(text, status, gate=False):
        if not color:
            return text
        return f"\033[{'34' if gate and status != 'done' else ANSI[status]}m{text}\033[0m"

    items = [i for i in all_items if i["status"] != "dropped"]
    tasks = [i for i in items if i["kind"] == "task"]
    gates = [i for i in items if i["kind"] == "gate"]
    title = args.title or core_title(args.core)
    stamp = updated.strftime("%Y-%m-%d %H:%M" if dated else "%H:%M") if updated else "no entries"
    sha = head(args.repo)
    out = [f"{title}  ·  ledger {stamp}" + (f"  ·  head {sha}" if sha else ""), ""]

    def counts(group):
        n = {s: sum(i["status"] == s for i in group) for s in STATUSES}
        extra = [f"{n['wip'] + n['review']} active"] if n["wip"] + n["review"] else []
        extra += [f"{n['held']} held"] if n["held"] else []
        return n["done"], len(group), extra

    releases = []
    for item in tasks:
        if item["release"] and item["release"] not in releases:
            releases.append(item["release"])
    rows = [("Plan", tasks)] + [(f"  {r}", [t for t in tasks if t["release"] == r]) for r in releases]
    label_width = max(len(name) for name, _ in rows) + 2
    for name, group in rows:
        done, total, extra = counts(group)
        line = f"{name:<{label_width}}{bar(done, total, args.width, args.ascii)} {done:>3}/{total:<3} merged"
        out.append(line + (f"  ·  {', '.join(extra)}" if extra else ""))
    if gates:
        out.append(f"{'Gates':<{label_width}}" + "  ".join(
            paint(f"{glyphs[g['status']]} {g['title']}", g["status"], gate=True) for g in gates))
    out.append("")

    lv = levels(items)
    width = shutil.get_terminal_size((100, 20)).columns
    last = max(lv.values(), default=0)
    settled = 0
    while settled < last and all(i["status"] == "done" for i in items if lv[i["id"]] == settled + 1):
        settled += 1
    if settled:
        merged = sum(lv[i["id"]] <= settled for i in items)
        span = f"1-{settled}" if settled > 1 else "1"
        out.append(paint(f"{span:>5}  {glyphs['done']} all {merged} merged", "done"))
    untouched = last
    while untouched > settled + 1 and all(i["status"] == "todo" for i in items if lv[i["id"]] == untouched):
        untouched -= 1
    if untouched < last - 1:
        tail = [(f"{untouched + 1}-{last}", [i for i in items if lv[i["id"]] > untouched])]
    else:
        untouched = last
        tail = []
    rows = [(str(n), [i for i in items if lv[i["id"]] == n]) for n in range(settled + 1, untouched + 1)]
    for label, members in rows + tail:
        cells = [paint(f"{glyphs[i['status']]} {i['id']}", i["status"], gate=i["kind"] == "gate")
                 for i in members]
        prefix, line = f"{label:>5}  ", ""
        for cell in cells:
            visible = len(re.sub(r"\033\[[\d;]*m", "", line + cell))
            if line and len(prefix) + visible + 2 > width:
                out.append(prefix + line.rstrip())
                prefix, line = " " * 7, ""
            line += cell + "  "
        out.append(prefix + line.rstrip())

    status = {i["id"]: i["status"] for i in all_items}
    ready = [i["id"] for i in items if i["status"] == "todo"
             and all(status.get(d) in ("done", "dropped", None) for d in i["deps"])]
    held = [f"{i['id']} ({i['note']})" if i["note"] else i["id"] for i in items if i["status"] == "held"]
    out.append("")
    if ready:
        out.append(f"Next up   {', '.join(ready)}")
    if held:
        out.append(f"Held      {'; '.join(held)}")
    out.append("   ".join(f"{glyphs[s]} {WORDS[s]}" for s in STATUSES) + "   gates in blue" * color)
    print("\n".join(out))


def minutes(delta):
    total = int(delta.total_seconds() // 60)
    return f"{total // 60}h{total % 60:02d}" if total >= 60 else f"{total}m"


def cmd_times(args):
    items, _, _ = load(args.core, args.ledger)
    started = sorted((i for i in items if i["start"]), key=lambda i: (i["start"], i["order"]))
    print("| Item | Dispatch | Merge | Wall | Fix rounds |")
    print("|---|---|---|---|---|")
    for item in started:
        end = item["end"]
        wall = minutes(end - item["start"]) if end else ""
        print(f"| {item['id']} | {item['start']:%H:%M} | {f'{end:%H:%M}' if end else ''} | {wall} "
              f"| {item['fixes']} |")
    ends = [i["end"] for i in items if i["end"]]
    if started and ends:
        tasks = [i for i in items if i["kind"] == "task" and i["status"] != "dropped"]
        merged = sum(1 for i in tasks if i["status"] == "done")
        print(f"\n{merged}/{len(tasks)} tasks merged in {minutes(max(ends) - started[0]['start'])} "
              f"from the first dispatch; {sum(i['fixes'] for i in items)} fix rounds; "
              f"{sum(1 for i in started if i['fixes'] == 0 and i['end'])} passed without a fix.")


def cmd_mermaid(args):
    items, _, _ = load(args.core, args.ledger)
    lines = ["```mermaid", "flowchart LR"]
    lines += [f"    classDef {name} {style}" for name, style in MERMAID_CLASS.items()]
    lines.append("")
    groups = {}
    for item in items:
        groups.setdefault(item["release"], []).append(item)
    for n, (release, members) in enumerate(groups.items()):
        indent = "    "
        if release:
            lines.append(f'    subgraph release_{n}["{release}"]')
            indent = "        "
        for item in members:
            title = item["title"].replace('"', "'")
            label = f"{item['id']} {title}" if item["kind"] == "task" else title
            lines.append(f'{indent}{item["id"]}["{label}"]')
        if release:
            lines.append("    end")
    ids = {i["id"] for i in items}
    lines += [f"    {d} --> {i['id']}" for i in items for d in i["deps"] if d in ids]
    lines.append("")
    by_class = {}
    for item in items:
        name = "gate" if item["kind"] == "gate" and item["status"] in ("todo", "wip", "review") else item["status"]
        by_class.setdefault(name, []).append(item["id"])
    lines += [f"    class {','.join(v)} {k}" for k, v in by_class.items()]
    lines.append("```")
    print("\n".join(lines))


def cmd_table(args):
    items, _, _ = load(args.core, args.ledger)
    print("| Task | Title | Release | Status |")
    print("|---|---|---|---|")
    for item in sorted(items, key=lambda i: i["order"]):
        if item["kind"] != "task":
            continue
        title = f"[{item['title']}]({args.link.rstrip('/')}/{item['file']})" if item["file"] else item["title"]
        status = WORDS[item["status"]] + (f" ({item['note']})" if item["note"] else "")
        print(f"| {item['id']} | {title} | {item['release'] or ''} | {status} |")


def cmd_add(args):
    now = datetime.datetime.now(ZoneInfo(args.tz) if args.tz else None)
    last_day = None
    if os.path.exists(args.ledger):
        with open(args.ledger, encoding="utf-8") as f:
            for line in f:
                dm = DAY.match(line)
                if dm:
                    last_day = dm.group(1)
    today = now.date().isoformat()
    with open(args.ledger, "a", encoding="utf-8") as f:
        if last_day != today:
            f.write(f"\n## {today}\n")
        f.write(f"- {now:%H:%M} {' '.join(args.text)}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, run in (("show", cmd_show), ("times", cmd_times), ("mermaid", cmd_mermaid), ("table", cmd_table)):
        p = sub.add_parser(name)
        p.add_argument("core")
        p.add_argument("ledger")
        p.set_defaults(run=run)
        if name == "show":
            p.add_argument("--ascii", action="store_true")
            p.add_argument("--color", choices=("auto", "always", "never"), default="auto")
            p.add_argument("--repo", default=".")
            p.add_argument("--width", type=int, default=20)
            p.add_argument("--title")
        if name == "table":
            p.add_argument("--link", required=True)
    p = sub.add_parser("add")
    p.add_argument("ledger")
    p.add_argument("text", nargs="+")
    p.add_argument("--tz")
    p.set_defaults(run=cmd_add)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
