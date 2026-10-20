"""Two dry-runs compared record by record, as micro.py does: prints `same` or the lists that differ.

    python3 same.py A.json.gz B.json.gz
"""
import gzip
import json
import sys
from collections import Counter

SKIP = {"repo", "counts"}


def records(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        payload = json.load(f)
    return {k: Counter(json.dumps(x, sort_keys=True, default=str) for x in v)
            for k, v in payload.items() if k not in SKIP and isinstance(v, list)}


a, b = records(sys.argv[1]), records(sys.argv[2])
bad = {k: (sum((a.get(k, Counter()) - b.get(k, Counter())).values()), sum((b.get(k, Counter()) - a.get(k, Counter())).values()))
       for k in set(a) | set(b) if a.get(k) != b.get(k)}
print("same" if not bad else "DIFFERS " + " ".join(f"{k}:-{x}+{y}" for k, (x, y) in sorted(bad.items())))
sys.exit(1 if bad else 0)
