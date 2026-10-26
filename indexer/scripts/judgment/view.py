"""For each site (JSON lines on stdin, with repo, file, line, receiver): the declaration the tree's answer reads, and
for a `call:` type the signatures of functions of that name in the repo."""
import json, os, re, sys
sys.path.insert(0, "/code")
from tree_sitter_language_pack import get_parser
from aidd_indexer.languages.go import locals as L
from aidd_indexer.tree import walk, node_text
parser = get_parser("go")
sigs = {}


def signatures(repo, name):
    if (repo, name) not in sigs:
        pat = re.compile(rb"^func (\([^)]*\) )?" + re.escape(name.encode()) + rb"[\[(]")
        found = []
        for d, dirs, files in os.walk(f"/repos/{repo}"):
            dirs[:] = [x for x in dirs if x not in (".git", "vendor", "node_modules")]
            for f in files:
                if f.endswith(".go"):
                    for ln in open(os.path.join(d, f), "rb"):
                        if pat.match(ln):
                            found.append(os.path.relpath(os.path.join(d, f), f"/repos/{repo}") + ": " + ln.decode(errors="replace").strip()[:150])
        sigs[(repo, name)] = found
    return sigs[(repo, name)]


for line in sys.stdin:
    d = json.loads(line)
    src = open(f"/repos/{d['repo']}/{d['file']}", "rb").read()
    tree = parser.parse(src)
    base = d["receiver"].split(".")[0]
    use = next((n for n in walk(tree.root_node) if n.type == "identifier" and n.start_point[0] + 1 == d["line"]
                and node_text(n, src) == base), None)
    print(f"\n## {d['repo']} {d['file']}:{d['line']} [{d['case']} / {d['kind']}] {d['receiver']}: {d['old']} -> {d['new']}")
    print("   use : " + src.splitlines()[d["line"] - 1].decode(errors="replace").strip()[:150])
    if use is None:
        print("   (no identifier at that line)"); continue
    top, n = None, use.parent
    while n is not None:
        if n.type in L.FUNCTIONS: top = n
        n = n.parent
    decls = L._DECLARATIONS.get(top, src).get(base, ()) if top is not None else ()
    for scope, end, typ in decls:
        row = src[:end].count(b"\n") + 1
        print(f"   decl line {row} -> {typ}: " + src.splitlines()[row - 1].decode(errors="replace").strip()[:130])
    t = d["new"] or ""
    if t.startswith("call:"):
        fn = t[5:].split("#")[0].rsplit(".", 1)[-1]
        for s in signatures(d["repo"], fn)[:3]:
            print("   sig : " + s)
    for k in ("was", "now"):
        if k in d: print(f"   {k}: {d[k]}")
