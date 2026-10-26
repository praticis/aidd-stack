"""Each sampled site (JSON lines on stdin): its source line, read as text, and its edges before and after.
   show.py REPOS_DIR < SAMPLES"""
import json
import sys

root = sys.argv[1]
for line in sys.stdin:
    d = json.loads(line)
    try:
        with open(f"{root}/{d['repo']}/{d['file']}", encoding="utf-8", errors="replace") as fh:
            text = fh.read().splitlines()[d["line"] - 1].strip()[:150]
    except (OSError, IndexError):
        text = "?"
    print(f"\n## [{d['kind']}] {d['repo']} {d['file']}:{d['line']}\n   {text}")
    print(f"   was {[tuple(e) for e in d['was']]}\n   now {[tuple(e) for e in d['now']]}")
