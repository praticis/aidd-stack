#!/usr/bin/env python3
"""Calibration corpus for the HTTP integration extractor (aidd_indexer/core/integrations.py + languages/<lang>/http.py).

Clones public repositories across Go / TypeScript / C# / Python frameworks and prints, per
repo, how many routes and outbound calls the extractor finds — a regression check that the
heuristics do not drift towards one team's style. Needs network + the grammars cached
(run inside the indexer image, or with TREE_SITTER_LANGUAGE_PACK_CACHE_DIR set).

    python scripts/http_corpus.py [--dir /tmp/aidd-corpus] [--json out/] [repo-name ...]

Expected order of magnitude (2026-09): chi 26 routes · gin-examples 31 · fiber-recipes 135 ·
alertmanager 22 · express 33 · nest 124 · eShop 23 routes + 6 calls · fastapi docs 87 ·
fastapi-template 19 · flask examples 12. Zero for gorilla-mux (library only) and for
jasontaylordev/CleanArchitecture (routes derived from method names by convention — not
extractable statically).
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CORPUS = {
    "chi": "go-chi/chi", "fiber-recipes": "gofiber/recipes", "gin-examples": "gin-gonic/examples",
    "gin-realworld": "gothinkster/golang-gin-realworld-example-app", "alertmanager": "prometheus/alertmanager",
    "gorilla-mux": "gorilla/mux",
    "nest": "nestjs/nest", "express": "expressjs/express", "express-realworld": "gothinkster/node-express-realworld-example-app",
    "fastify": "fastify/fastify",
    "eshop": "dotnet/eShop", "clean-arch-dotnet": "jasontaylordev/CleanArchitecture",
    "fastapi": "tiangolo/fastapi", "fastapi-template": "fastapi/full-stack-fastapi-template", "flask": "pallets/flask",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="/tmp/aidd-corpus")
    ap.add_argument("--json", default=None, help="directory to dump per-repo candidates as JSON")
    ap.add_argument("repos", nargs="*")
    args = ap.parse_args()
    os.environ.setdefault("AIDD_TENANT", "corpus")
    from aidd_indexer.cli import extract_tree
    from aidd_indexer.core.integrations import extract_http
    from aidd_indexer.core.model import RepoInfo

    base = Path(args.dir)
    base.mkdir(parents=True, exist_ok=True)
    for name in args.repos or sorted(CORPUS):
        dest = base / name
        if not dest.exists():
            subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{CORPUS[name]}.git", str(dest)], check=False)
        repo = RepoInfo(tenant="corpus", name=name, ref="main", commit_sha="x", root=str(dest))
        t0 = time.time()
        with contextlib.redirect_stderr(io.StringIO()):
            res, extractors = extract_tree(repo)
            hr = extract_http(repo, extractors)
        fw = collections.Counter(e.framework for e in hr.endpoints)
        via = collections.Counter(c.via.split(".")[-1] for c in hr.calls)
        with_handler = sum(1 for e in hr.endpoints if e.handler_id)
        print(f"{name:20} {len(res.files):5} files | routes {len(hr.endpoints):4} (handler {with_handler:4}) {dict(fw)} "
              f"| calls {len(hr.calls):4} {dict(via.most_common(5))} | warn {len(hr.warnings)} | {time.time()-t0:.1f}s")
        if args.json:
            Path(args.json).mkdir(parents=True, exist_ok=True)
            (Path(args.json) / f"{name}.json").write_text(json.dumps(
                {"endpoints": [e.__dict__ for e in hr.endpoints], "calls": [c.__dict__ for c in hr.calls], "warnings": hr.warnings},
                indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
