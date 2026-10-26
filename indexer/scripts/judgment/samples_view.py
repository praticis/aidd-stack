"""chain_diff.py's seeded samples, each with its source line.   samples_view.py SAMPLES.jsonl REPOS_DIR"""
import json
import sys
from pathlib import Path

repos = Path(sys.argv[2])
for line in open(sys.argv[1]):
    d = json.loads(line)
    try:
        src = (repos / d["repo"] / d["file"]).read_text(errors="replace").splitlines()[d["line"] - 1].strip()[:130]
    except (OSError, IndexError):
        src = "?"
    short = lambda es: [(c.rsplit(".", 2)[-2] + "." + c.rsplit(".", 1)[-1] if "." in c else c, s) for c, s in es][:3]
    print(f"[{d.get('kind')}] {d['repo']} {d['file'].rsplit('/', 1)[-1]}:{d['line']}\n    {src}\n"
          f"    was {short(d.get('was', []))}\n    now {short(d.get('now', []))}")
