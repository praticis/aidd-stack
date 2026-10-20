"""Counts the kinds of reads each scan recorded, from a package-mode extraction of /repo at 1 worker."""
import collections
import os
import statistics
from pathlib import Path

os.environ.update(AIDD_BATCH="package", AIDD_WORKERS="1", AIDD_PIPELINE="1")
from aidd_indexer import cli  # noqa: E402

repo = cli.repo_info_for_checkout(Path("/repo"), "micro", None)
convs = cli.conventions_for(repo.tenant, repo.name)
rules = cli.conventions.dispatch_rules(convs)
res, sums = cli.extract_tree(repo, cli.conventions.scan_patterns(convs), cli.call_names(rules))
scans = [s for s in sums if s.scan is not None]
kinds = collections.Counter()
with_kind = collections.Counter()
per_scan = []
for s in scans:
    reads = s.scan[1]
    per_scan.append(len(reads))
    seen = set()
    for r, _ in reads:
        k = r[0] if r[0] != "view" else f"view:{r[1]}"
        kinds[k] += 1
        seen.add(k)
    for k in seen:
        with_kind[k] += 1
n = len(scans)
print(f"scans={n} reads per scan median={statistics.median(per_scan)} p90={sorted(per_scan)[int(n * 0.9)]} max={max(per_scan)}")
for k, c in sorted(with_kind.items(), key=lambda x: -x[1]):
    print(f"  {k:24} scans={c:6} ({100 * c / n:5.1f} %) reads={kinds[k]}")
