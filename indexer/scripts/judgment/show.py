"""Each sampled site (JSON lines on stdin, as chain_diff.py writes them to stderr): its source line, read as text, and
its edges before and after; with --short, the callees shortened to type and method.
   show.py REPOS_DIR [--short] < SAMPLES"""
import json
import sys


def source(root, d, width):
    try:
        with open(f"{root}/{d['repo']}/{d['file']}", encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()[d["line"] - 1].strip()[:width]
    except (OSError, IndexError):
        return "?"


def short(edges):
    return [(c.rsplit(".", 2)[-2] + "." + c.rsplit(".", 1)[-1] if "." in c else c, s) for c, s in edges][:3]


root, brief = sys.argv[1], "--short" in sys.argv[2:]
for line in sys.stdin:
    d = json.loads(line)
    if brief:
        print(f"[{d.get('kind')}] {d['repo']} {d['file'].rsplit('/', 1)[-1]}:{d['line']}\n    {source(root, d, 130)}\n"
              f"    was {short(d.get('was', []))}\n    now {short(d.get('now', []))}")
    else:
        print(f"\n## [{d['kind']}] {d['repo']} {d['file']}:{d['line']}\n   {source(root, d, 150)}")
        print(f"   was {[tuple(e) for e in d['was']]}\n   now {[tuple(e) for e in d['now']]}")
