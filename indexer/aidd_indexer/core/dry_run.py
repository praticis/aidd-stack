"""What `aidd index --dry-run --out` writes in place of the graph: the snapshot's records, list by list, as the
micro set and the live checks compare them."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .model import ExtractionResult
from .resolve import Resolved


def payload(res: ExtractionResult, rv: Resolved) -> dict[str, Any]:
    return {
        "repo": asdict(res.repo),
        "counts": res.counts() | {"calls_edges": len(rv.calls), "imports_edges": len(rv.imports), "packages": len(rv.packages),
                                  "hierarchy_edges": len(rv.hierarchy)},
        "modules": [asdict(m) for m in res.modules],
        "files": [asdict(f) for f in res.files],
        "symbols": [asdict(s) for s in res.symbols],
        "calls": [asdict(c) for c in rv.calls],
        "imports": [asdict(i) for i in rv.imports],
        "hierarchy": [asdict(e) for e in rv.hierarchy],
        "packages": [asdict(p) for p in rv.packages.values()],
        "endpoints": [asdict(e) for e in res.endpoints],
        "http_calls": [asdict(c) for c in res.http_calls],
        "violations": [asdict(v) for v in res.violations],
        "provides": [asdict(p) for p in res.provides],
        "requires": [asdict(d) for d in res.requires],
        "warnings": res.warnings,
    }
