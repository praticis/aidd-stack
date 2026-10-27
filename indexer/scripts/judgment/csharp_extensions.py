"""The edges to the repo's C# extension methods that change between two micro dry-runs. BEFORE and AFTER hold
`<repo>.json.gz`, as micro.sh and micro-fresh.sh leave them.

  csharp_extensions.py sites     BEFORE AFTER OUT.jsonl REPO...         one row per edge to an extension that went away:
                                                                        its strategy, what its `this` takes, what the site has now
  csharp_extensions.py back      LOST.jsonl AFTER OUT.jsonl             of those rows, which a later run has again; the rest by what the site has
  csharp_extensions.py classes   BEFORE AFTER REPOS_DIR N SEED REPO...  the changed sites by class of extension gained, N seeded samples per class
  csharp_extensions.py this-kind BEFORE AFTER REPOS_DIR REPO...         each `unique-name` edge gained to an extension: does its `this` take any value
  csharp_extensions.py blocks    BEFORE AFTER REPOS_DIR REPO...         per repo, the sites that lose an edge into a file with `extension(...)` blocks"""
import collections
import json
import os
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edges_lib import edges, load  # noqa: E402

THIS = re.compile(r"\(\s*(\[[^\]]*\]\s*)*this\s")
BLOCK = re.compile(r"^\s*extension(<[^>]*>)?\s*\(", re.M)


def kind_of(now):
    """What a site has: nothing, only inherited edges, a typed one, or a name match."""
    if not now:
        return "nothing"
    if all(s.startswith("inherited") for _, s in now):
        return "inherited"
    return "typed" if any(s.startswith("receiver-type") for _, s in now) else "name"


def sites(before, after, out, repos):
    kinds = collections.Counter()
    with open(out, "w") as fh:
        for repo in repos:
            b, a = load(before, repo), load(after, repo)
            sig = {s["qualified_name"]: s.get("signature") or "" for s in b["symbols"] + a["symbols"]
                   if s.get("kind") == "method" and "(this " in (s.get("signature") or "")}
            eb, ea = edges(b), edges(a)
            # sorted: a set's order changes from one process to the next, and so would the rows
            for site in sorted(eb.keys() | ea.keys()):
                was, now = eb.get(site, set()), ea.get(site, set())
                gone = {(c, s) for c, s in was - now if c in sig and c not in {x for x, _ in now}}
                for callee, strat in sorted(gone):
                    m = re.search(r"\(this\s+([\w.<>\[\]?, ]+?)\s+\w+\s*[,)]", sig[callee])
                    this = m.group(1) if m else "?"
                    kind = ("generic" if re.fullmatch(r"T\w*", this) else "object" if this == "object" else
                            "interface" if re.match(r"I[A-Z]", this) else "class")
                    kinds[(strat.replace("-ambiguous", "~"), kind)] += 1
                    fh.write(json.dumps({"repo": repo, "site": site, "callee": callee, "was": strat, "this": this,
                                         "kind": kind, "now": sorted(now)}) + "\n")
    for k, v in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0])):
        print(v, *k)
    print("all", sum(kinds.values()))


def back(lost, after, out):
    rows = [json.loads(line) for line in open(lost)]
    runs, count = {}, collections.Counter()
    with open(out, "w") as fh:
        for r in rows:
            if r["repo"] not in runs:
                runs[r["repo"]] = edges(load(after, r["repo"]))
            now = runs[r["repo"]].get(tuple(r["site"]), set())
            again = [s for c, s in now if c == r["callee"]]
            state = "back " + again[0].replace("-ambiguous", "~") if again else "lost, now " + kind_of(now)
            count[(state, r["kind"])] += 1
            fh.write(json.dumps(r | {"c7": sorted(now), "state": state}) + "\n")
    for k, v in sorted(count.items(), key=lambda kv: (kv[0][0], -kv[1], kv[0][1])):
        print(v, *k)
    print("all", sum(count.values()))


def classes(before, after, repos, n, seed, names):
    by_class = collections.defaultdict(list)
    for repo in names:
        b, a = load(before, repo), load(after, repo)
        ext = {s["qualified_name"] for s in a["symbols"]
               if s.get("kind") == "method" and (THIS.search(s.get("signature") or "")
                                                 or " static " in f" {s.get('signature') or ''} ")}
        eb, ea = edges(b), edges(a)
        # sorted: a set's order changes from one process to the next, and the seeded sample is drawn in this order
        for site in sorted(ea.keys() | eb.keys()):
            was, now = eb.get(site, set()), ea.get(site, set())
            if was == now:
                continue
            new = now - was
            gained = {(c, s) for c, s in new if c in ext}
            if not gained:
                cls = "other: " + ("removed only" if not new else "added non-extension")
            else:
                strat = "name" if all(s == "unique-name" for _, s in gained) else "typed"
                cls = f"extension {strat}, was {kind_of(was)}"
            by_class[cls].append((repo, site, sorted(was), sorted(now)))
    rnd = random.Random(seed)
    for cls, rows in sorted(by_class.items(), key=lambda kv: -len(kv[1])):
        print(f"== {cls}: {len(rows)} sites, {dict(collections.Counter(r[0] for r in rows).most_common())}")
        for repo, (f, line), was, now in rnd.sample(rows, min(n, len(rows))):
            src = (repos / repo / f).read_text(errors="replace").splitlines()[line - 1].strip()[:150]
            short = lambda es: [(c.split(".")[-2] + "." + c.split(".")[-1], s) for c, s in es][:3]
            print(f"  {repo} {f}:{line}\n      {src}\n      was {short(was)}\n      now {short(now)}")


def this_kind(before, after, repos, names):
    groups = collections.defaultdict(list)
    for repo in names:
        b, a = load(before, repo), load(after, repo)
        files = {f["id"]: f["path"] for f in a["files"]}
        sym = {s["qualified_name"]: s for s in a["symbols"]}
        eb, ea = edges(b), edges(a)
        for site, now in ea.items():
            for callee, strat in now - eb.get(site, set()):
                if strat != "unique-name" or callee not in sym:
                    continue
                s = sym[callee]
                lines = (repos / repo / files[s["file_id"]]).read_text(errors="replace").splitlines()
                head = " ".join(lines[s["line_start"] - 1:s["line_start"] + 4])
                m = re.search(r"\(\s*(?:\[[^\]]*\]\s*)*this\s+([^,)]+?)\s+\w+\s*[,)=]", head)
                this = m.group(1) if m else "?"
                tps = re.search(r"\b" + re.escape(s["name"]) + r"\s*<([^>(]*)>\s*\(", head)
                own = {t.strip() for t in tps.group(1).split(",")} if tps else set()
                kind = "any" if this.rstrip("?") in own or this.rstrip("?") == "object" else "type"
                src = (repos / repo / site[0]).read_text(errors="replace").splitlines()[site[1] - 1].strip()[:110]
                groups[kind].append((repo, site, callee.split(".")[-2] + "." + s["name"], this, src))
    for kind, rows in groups.items():
        print(f"== {kind}: {len(rows)}")
        for repo, site, callee, this, src in sorted(rows):
            print(f"  {repo} {site[0].split('/')[-1]}:{site[1]} {callee}(this {this})\n      {src}")


def blocks(before, after, repos, names):
    for repo in names:
        has_block = {}

        def blocky(path):
            if path not in has_block:
                try:
                    has_block[path] = bool(BLOCK.search((repos / repo / path).read_text(errors="replace")))
                except OSError:
                    has_block[path] = False
            return has_block[path]

        sides = []
        for run in (load(before, repo), load(after, repo)):
            files = {f["id"]: f["path"] for f in run["files"]}
            sym = {s["id"]: s for s in run["symbols"]}
            out = collections.defaultdict(set)
            for c in run["calls"]:
                caller, callee = sym.get(c["caller_id"]), sym.get(c["callee_id"])
                if caller is None or callee is None:
                    continue
                out[(files[caller["file_id"]], c["line"])].add((callee["qualified_name"], files[callee["file_id"]]))
            sides.append(out)
        b, h = sides
        lost, emptied = 0, 0
        for key, was in b.items():
            now = h.get(key, set())
            gone = [e for e in was - now if blocky(e[1])]
            lost += bool(gone)
            emptied += bool(gone) and not now
        print(f"{repo}: sites losing an edge into a file with extension blocks {lost}, left with none {emptied}")


COMMANDS = {
    "sites": lambda a: sites(a[0], a[1], a[2], a[3:]),
    "back": lambda a: back(a[0], a[1], a[2]),
    "classes": lambda a: classes(a[0], a[1], Path(a[2]), int(a[3]), int(a[4]), a[5:]),
    "this-kind": lambda a: this_kind(a[0], a[1], Path(a[2]), a[3:]),
    "blocks": lambda a: blocks(a[0], a[1], Path(a[2]), a[3:]),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]](sys.argv[2:])
