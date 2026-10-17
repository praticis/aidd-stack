#!/usr/bin/env python3
"""Measurement for the HTTP corpus (`scripts/http_corpus.py`): ids and diffs between two runs,
precision/recall against a gabarito (`tests/corpus_expected/<repo>.json`), OpenAPI → gabarito and
reproducible samples for manual checking. Pure functions over a run (the per-repo JSON the corpus
writes) — no tree-sitter, no network.

Gabarito, one per repo:

    {"source": "openapi" | "routes-dump" | "manual",     # or per kind, like scope
     "sha": "<pinned commit it was read from>",
     "spec": ["openapi.yaml"],                          # optional: where the expected routes came from
     "scope": ["src/Catalog.API/"],                     # optional: only extracted items under these count —
                                                        # or per kind: {"endpoints": [...], "calls": [...]}
     "scope_paths": ["/api/v2/", "/healthz"],           # optional: and only extracted items under these paths —
                                                        # when a spec covers one URL subspace and the same files
                                                        # serve others (a web UI); also per kind
     "endpoints": [{"method": "GET", "path": "/api/items/{id}", "category": null}],   # category: why it is missed
     "calls":     [{"method": "GET", "path": "/api/items/{id}"}],   # literal/template paths only, as written
     "checked":   {"endpoints": [{"evidence": "repo:file:line", "method": "GET", "path": "/x", "ok": true,
                                  "category": null}], "calls": [...]},
     "language": {"calls": "TS/JS"},                     # optional: a kind written in another language than the
                                                        # repo's (a Go server's React UI) — for the per-language summary
     "notes": "..."}

Matching is by `(method, path_key)` over distinct pairs: placeholder names do not matter, and an
extracted ANY matches every method of the same path (and the other way round). A kind that is absent
from the gabarito is not measured; present and empty means nothing is expected. `checked` is the
manual sample of extracted items over the whole repo (H2-D6): precision = ok / checked with a verdict.

    python scripts/corpus_metrics.py from-openapi spec.yaml [more.yaml ...] [--prefix /api] [--scope dir/] [--sha X]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from aidd_indexer.core.paths import HTTP_METHODS, normalize_path, path_key

KINDS = ("endpoints", "calls")
SECONDARY = {"endpoints": "handler_id", "calls": "caller_id"}      # same id, different resolution


def evidence_file(evidence: str) -> str:
    """`repo:path/to/file.go:12` → `path/to/file.go`."""
    return evidence.rsplit(":", 1)[0].split(":", 1)[-1]


def item_key(item: dict) -> tuple[str, str]:
    return item["method"].upper(), path_key(normalize_path(item["path"]))


def run_ids(run: dict, kind: str) -> dict[tuple[str, str, str], dict]:
    """`(method, path_key, evidence)` → item: what a diff between two runs compares."""
    return {(*item_key(x), x["evidence"]): x for x in run.get(kind, [])}


@dataclass
class Diff:
    removed: list[tuple] = field(default_factory=list)
    added: list[tuple] = field(default_factory=list)
    resolution: list[tuple] = field(default_factory=list)     # same id, handler/caller changed

    def __bool__(self) -> bool:
        return bool(self.removed or self.added or self.resolution)


def diff_runs(old: dict, new: dict, kind: str) -> Diff:
    a, b = run_ids(old, kind), run_ids(new, kind)
    attr = SECONDARY[kind]
    return Diff(sorted(a.keys() - b.keys()), sorted(b.keys() - a.keys()),
                sorted(k for k in a.keys() & b.keys() if a[k].get(attr) != b[k].get(attr)))


def _matches(a: tuple[str, str], b: tuple[str, str]) -> bool:
    return a[1] == b[1] and (a[0] == b[0] or "ANY" in (a[0], b[0]))


@dataclass
class Score:
    extracted: int
    expected: int
    false_positives: list[tuple[str, str]]
    false_negatives: list[tuple[str, str]]

    @property
    def precision(self) -> float | None:
        return (self.extracted - len(self.false_positives)) / self.extracted if self.extracted else None

    @property
    def recall(self) -> float | None:
        return (self.expected - len(self.false_negatives)) / self.expected if self.expected else None


def score(run: dict, gabarito: dict, kind: str) -> Score | None:
    if kind not in gabarito:
        return None
    scope = gabarito.get("scope") or ()
    scope = tuple((scope.get(kind) or ()) if isinstance(scope, dict) else scope)
    paths = gabarito.get("scope_paths") or ()
    paths = tuple((paths.get(kind) or ()) if isinstance(paths, dict) else paths)
    x = {item_key(i) for i in run.get(kind, []) if (not scope or evidence_file(i["evidence"]).startswith(scope))
         and (not paths or _under(normalize_path(i["path"]), paths))}
    e = {item_key(i) for i in gabarito[kind]}
    return Score(len(x), len(e), sorted(k for k in x if not any(_matches(k, j) for j in e)),
                 sorted(k for k in e if not any(_matches(k, j) for j in x)))


def _under(path: str, prefixes: tuple[str, ...]) -> bool:
    """`/v1/items` is under `/v1/` and `/v1`; `/v10` is not."""
    return any(path == p.rstrip("/") or path.startswith(p.rstrip("/") + "/") for p in prefixes)


def miss_categories(gabarito: dict, kind: str, sc: Score) -> dict[tuple[str, str], str | None]:
    """Each false negative → the `category` its expected entry records (why it is missed), if any."""
    cats: dict[tuple[str, str], str | None] = {}
    for item in gabarito.get(kind, []):
        key = item_key(item)
        if key in sc.false_negatives and not cats.get(key):
            cats[key] = item.get("category")
    return {k: cats.get(k) for k in sc.false_negatives}


def _check_id(item: dict) -> tuple[str, str, str]:
    return item["evidence"], item["method"].upper(), normalize_path(item["path"])


@dataclass
class Checked:
    ok: int
    judged: int
    pending: int                       # sampled, no verdict yet
    stale: list[dict]                  # judged items the run no longer has — re-sample
    wrong: list[dict]                  # ok: false, with their category

    @property
    def precision(self) -> float | None:
        return self.ok / self.judged if self.judged else None


def checked_precision(run: dict, gabarito: dict, kind: str) -> Checked | None:
    items = (gabarito.get("checked") or {}).get(kind)
    if not items:
        return None
    present = {_check_id(x) for x in run.get(kind, [])}
    judged = [i for i in items if i.get("ok") is not None]
    return Checked(sum(1 for i in judged if i["ok"]), len(judged), len(items) - len(judged),
                   [i for i in judged if _check_id(i) not in present], [i for i in judged if not i["ok"]])


def sample(run: dict, kind: str, n: int, seed: int | str, name: str) -> list[dict]:
    """`n` items drawn with a fixed seed per repo and kind, as `checked` entries awaiting a verdict."""
    items = sorted(run.get(kind, []), key=_check_id)
    pick = random.Random(f"{seed}:{name}:{kind}").sample(items, min(n, len(items)))
    return [{"evidence": x["evidence"], "method": x["method"], "path": x["path"],
             "raw": x.get("raw_pattern") or x.get("raw_path"), "ok": None, "category": None}
            for x in sorted(pick, key=_check_id)]


def openapi_prefix(spec: dict) -> str:
    """Swagger 2 `basePath`, or the path of the first OpenAPI 3 `servers[].url`."""
    if spec.get("basePath"):
        return spec["basePath"]
    url = ((spec.get("servers") or [{}])[0] or {}).get("url") or ""
    return urlparse(url).path if "://" in url else url


def from_openapi(spec: dict, prefix: str | None = None, base: Path | None = None) -> list[dict]:
    """Every `(method, path)` the spec declares, with the server prefix applied. A path item that is a
    `$ref` to another file (`/ping: {$ref: 'write/ping.yaml'}`) is read from `base`, the spec's folder."""
    pre = openapi_prefix(spec) if prefix is None else prefix
    pre = "/" + pre.strip("/") if pre.strip("/") else ""
    out = set()
    for p, ops in (spec.get("paths") or {}).items():
        if isinstance(ops, dict) and base is not None and str(ops.get("$ref", "#")).split("#")[0]:
            ops = load_spec(base / ops["$ref"].split("#")[0])
        if isinstance(ops, dict):
            out |= {(m.upper(), normalize_path(pre + p)) for m in ops if m.upper() in HTTP_METHODS}
    return [{"method": m, "path": p} for m, p in sorted(out, key=lambda t: (t[1], t[0]))]


def load_spec(path: Path) -> dict:
    text = path.read_text()
    if path.suffix == ".json":
        return json.loads(text)
    import yaml
    return yaml.safe_load(text)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    oa = sub.add_parser("from-openapi", help="print a gabarito with the routes an OpenAPI/Swagger spec declares")
    oa.add_argument("spec", type=Path, nargs="+", help="several specs (API versions) → their union")
    oa.add_argument("--prefix", default=None, help="override the basePath/servers prefix ('' for none)")
    oa.add_argument("--scope", action="append", default=[], help="file prefix the extracted routes must be under")
    oa.add_argument("--sha", default="")
    args = ap.parse_args()
    routes = {(r["method"], r["path"]): r for sp in args.spec for r in from_openapi(load_spec(sp), args.prefix, sp.parent)}
    gab = {"source": "openapi", "sha": args.sha, "spec": [str(sp) for sp in args.spec],
           "endpoints": [routes[k] for k in sorted(routes, key=lambda t: (t[1], t[0]))]}
    if args.scope:
        gab["scope"] = args.scope
    json.dump(gab, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
