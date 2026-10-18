"""Track a plan's progress in one state file and render it.

  python3 progress.py sync STATE --plan PLAN [--prefix "Task "] [--title TEXT]
  python3 progress.py set STATE ID... --status STATUS [--release NAME] [--note TEXT]
  python3 progress.py add STATE ID --title TEXT [--gate] [--after IDS] [--before IDS] [--release NAME]
  python3 progress.py show STATE [--ascii] [--color auto|always|never] [--repo DIR]
  python3 progress.py mermaid STATE
  python3 progress.py table STATE --link PATH

sync reads the plan's task headings and the first Mermaid flowchart in it (edges, and
subgraphs as releases), keeps every known status, adds new nodes and marks nodes gone from
the plan as dropped. Graph nodes without a task heading are gates (reviews, live steps,
external milestones). STATUS is one of: todo, wip, review, done, held, dropped.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

STATUSES = ("todo", "wip", "review", "done", "held", "dropped")
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

HEADING = re.compile(r"(#{1,6})\s+(.+?)\s*#*\s*$")
CODE = re.compile(r"(?:Task\s+)?([A-Za-z]*\d+[A-Za-z]?)\s*[:.]\s*(.+)")
NODE = re.compile(r"^([A-Za-z_][\w-]*)\s*(?:\[\"?(.*?)\"?\]|\(\"?(.*?)\"?\)|\{\"?(.*?)\"?\})?$")
ARROW = re.compile(r"\s*(?:<?-->|<?==>|-\.->|---|--[^-<>|]+-->)\s*")


def slug(text):
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")


def unfenced(lines):
    fence = None
    for line in lines:
        marker = line.lstrip()[:3]
        if marker in ("```", "~~~"):
            fence = marker if fence is None else (None if marker == fence else fence)
            yield line, True
            continue
        yield line, fence is not None


def plan_tasks(text, prefix):
    seen, tasks = {}, []
    for line, fenced in unfenced(text.splitlines()):
        m = None if fenced else HEADING.match(line)
        if not m:
            continue
        heading = m.group(2)
        base = slug(heading)
        count = seen.get(base, 0)
        seen[base] = count + 1
        if not heading.startswith(prefix):
            continue
        cm = CODE.match(heading)
        code, title = (cm.group(1), cm.group(2)) if cm else (heading, heading)
        tasks.append({"code": code, "title": title, "anchor": base if count == 0 else f"{base}-{count}"})
    return tasks


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
                ids.append(node_id)
            groups.append(ids)
        for left, right in zip(groups, groups[1:]):
            edges += [(a, b) for a in left for b in right]
    return nodes, edges


def match_heading(node_id, label, by_code):
    for key in (node_id, label, label.split()[0] if label else ""):
        if key in by_code:
            return by_code[key]
    m = re.fullmatch(r"[Tt](\d+)", node_id)
    return by_code.get(m.group(1)) if m else None


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, state):
    state["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def cmd_sync(args):
    with open(args.plan, encoding="utf-8") as f:
        text = f.read()
    tasks = plan_tasks(text, args.prefix)
    nodes, edges = plan_graph(text)
    by_code = {t["code"]: t for t in tasks}
    order = {t["code"]: n for n, t in enumerate(tasks)}
    old = load(args.state) if os.path.exists(args.state) else {"items": []}
    known = {i["id"]: i for i in old["items"]}
    items, used = [], set()
    for node_id, node in nodes.items():
        task = match_heading(node_id, node["label"], by_code)
        if task:
            used.add(task["code"])
        items.append({
            "id": node_id,
            "code": task["code"] if task else node_id,
            "title": task["title"] if task else node["label"],
            "anchor": task["anchor"] if task else None,
            "kind": "task" if task else "gate",
            "release": node["release"],
            "deps": sorted({a for a, b in edges if b == node_id}),
        })
    t_style = any(re.fullmatch(r"T\d+", n) for n in nodes)
    for task in tasks:
        if task["code"] in used:
            continue
        task_id = f"T{task['code']}" if t_style and task["code"].isdigit() else task["code"]
        host = next((n for n, node in nodes.items()
                     if re.search(rf"\b({re.escape(task_id)}|{re.escape(task['code'])})\b", node["label"])), None)
        items.append({"id": task_id, "code": task["code"], "title": task["title"], "anchor": task["anchor"],
                      "kind": "task", "release": nodes[host]["release"] if host else None,
                      "deps": sorted({a for a, b in edges if b == host}) if host else []})
    for item in items:
        item["order"] = order.get(item["code"], len(order))
        prev = known.pop(item["id"], {})
        item["status"] = prev.get("status", "todo")
        item["note"] = prev.get("note", "")
        if prev.get("moved"):
            item["release"], item["moved"] = prev["release"], True
        if prev.get("added"):
            item.update(added=True, deps=prev["deps"])
    for gone in known.values():
        if gone.get("added"):
            items.append(gone)
        elif gone["status"] != "dropped":
            items.append({**gone, "status": "dropped", "note": gone.get("note") or "gone from the plan"})
    state = {"title": args.title or old.get("title") or os.path.basename(args.plan), "plan": args.plan, "items": items}
    save(args.state, state)
    print(f"{len(items)} items, {sum(i['kind'] == 'task' for i in items)} tasks, {len(edges)} edges")


def find(state, ids):
    index = {i["id"]: i for i in state["items"]}
    missing = [i for i in ids if i not in index]
    if missing:
        sys.exit(f"unknown id: {', '.join(missing)}")
    return [index[i] for i in ids]


def cmd_set(args):
    state = load(args.state)
    for item in find(state, args.ids):
        if args.status:
            item["status"] = args.status
        if args.release is not None:
            item["release"], item["moved"] = args.release, True
        if args.note is not None:
            item["note"] = args.note
    save(args.state, state)


def cmd_add(args):
    state = load(args.state)
    if any(i["id"] == args.id for i in state["items"]):
        sys.exit(f"{args.id} exists; use set")
    after = args.after.split(",") if args.after else []
    find(state, after)
    state["items"].append({"id": args.id, "code": args.id, "title": args.title, "anchor": None,
                           "kind": "gate" if args.gate else "task", "release": args.release,
                           "deps": after, "status": "todo", "note": "", "added": True})
    for item in find(state, args.before.split(",") if args.before else []):
        item["deps"] = sorted(set(item["deps"]) | {args.id})
        item["added"] = True
    save(args.state, state)


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
    state = load(args.state)
    color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty() and not os.environ.get("NO_COLOR"))
    glyphs = ASCII_GLYPH if args.ascii else GLYPH

    def paint(text, status, gate=False):
        if not color:
            return text
        return f"\033[{'34' if gate and status != 'done' else ANSI[status]}m{text}\033[0m"

    items = [i for i in state["items"] if i["status"] != "dropped"]
    tasks = [i for i in items if i["kind"] == "task"]
    gates = [i for i in items if i["kind"] == "gate"]
    updated = datetime.datetime.fromisoformat(state["updated"]).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    sha = head(args.repo)
    out = [f"{state['title']}  ·  updated {updated}" + (f"  ·  head {sha}" if sha else ""), ""]

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

    status = {i["id"]: i["status"] for i in state["items"]}
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


def cmd_mermaid(args):
    state = load(args.state)
    items = state["items"]
    lines = ["```mermaid", "flowchart LR"]
    lines += [f"    classDef {name} {style}" for name, style in MERMAID_CLASS.items()]
    lines.append("")
    groups = {}
    for item in items:
        groups.setdefault(item["release"], []).append(item)

    def node(item):
        title = item["title"].replace('"', "'")
        return f'{item["id"]}["{item["code"]} {title}"]' if item["kind"] == "task" else f'{item["id"]}["{title}"]'

    for n, (release, members) in enumerate(groups.items()):
        indent = "    "
        if release:
            lines.append(f'    subgraph release_{n}["{release}"]')
            indent = "        "
        lines += [indent + node(i) for i in members]
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
    state = load(args.state)
    print("| Code | Task | Release | Status |")
    print("|---|---|---|---|")
    for item in sorted(state["items"], key=lambda i: i.get("order", len(state["items"]))):
        if item["kind"] != "task":
            continue
        title = f"[{item['title']}]({args.link}#{item['anchor']})" if item["anchor"] else item["title"]
        status = WORDS[item["status"]] + (f" ({item['note']})" if item["note"] else "")
        print(f"| {item['code']} | {title} | {item['release'] or ''} | {status} |")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("sync")
    p.add_argument("state")
    p.add_argument("--plan", required=True)
    p.add_argument("--prefix", default="Task ")
    p.add_argument("--title")
    p.set_defaults(run=cmd_sync)
    p = sub.add_parser("set")
    p.add_argument("state")
    p.add_argument("ids", nargs="+")
    p.add_argument("--status", choices=STATUSES)
    p.add_argument("--release")
    p.add_argument("--note")
    p.set_defaults(run=cmd_set)
    p = sub.add_parser("add")
    p.add_argument("state")
    p.add_argument("id")
    p.add_argument("--title", required=True)
    p.add_argument("--gate", action="store_true")
    p.add_argument("--after")
    p.add_argument("--before")
    p.add_argument("--release")
    p.set_defaults(run=cmd_add)
    p = sub.add_parser("show")
    p.add_argument("state")
    p.add_argument("--ascii", action="store_true")
    p.add_argument("--color", choices=("auto", "always", "never"), default="auto")
    p.add_argument("--repo", default=".")
    p.add_argument("--width", type=int, default=20)
    p.set_defaults(run=cmd_show)
    p = sub.add_parser("mermaid")
    p.add_argument("state")
    p.set_defaults(run=cmd_mermaid)
    p = sub.add_parser("table")
    p.add_argument("state")
    p.add_argument("--link", required=True)
    p.set_defaults(run=cmd_table)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
