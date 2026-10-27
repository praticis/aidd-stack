"""The CALLS edges of given sites in dry-runs: site_edges.py REPO FILE_SUFFIX:LINE[,..] DIR..."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edges_lib import edges, load  # noqa: E402

repo, sites = sys.argv[1], [s.rsplit(":", 1) for s in sys.argv[2].split(",")]
for d in sys.argv[3:]:
    e = edges(load(d, repo))
    print("==", d.rsplit("/", 1)[-1])
    for suffix, line in sites:
        for (f, ln), callees in e.items():
            if f.endswith(suffix) and ln == int(line):
                print(f"  {suffix}:{line}", sorted(callees))
