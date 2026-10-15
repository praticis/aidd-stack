#!/usr/bin/env python3
"""Calibration corpus for the HTTP integration extractor (aidd_indexer/core/integrations.py + languages/<lang>/http.py).

Clones public repositories across Go / TypeScript / C# / Python frameworks and prints, per
repo, how many routes and outbound calls the extractor finds — a regression check that the
heuristics do not drift towards one team's style. Needs network + the grammars cached
(run inside the indexer image, or with TREE_SITTER_LANGUAGE_PACK_CACHE_DIR set).

    python scripts/http_corpus.py [--dir ~/.cache/aidd-corpus/repos] [--json out/] [repo-name ...]

Every repo is pinned to a commit (`CORPUS`: name -> (slug, sha)) so a run is comparable with an
earlier one; bump a sha deliberately and re-run the baseline in the same change. Clones live outside
the repository (`--dir`, or `AIDD_CORPUS_DIR`) and are never versioned.

Baseline at the pinned commits (2026-10-14, indexer 0.2.14): alertmanager 22 routes · chi 25 ·
fiber-recipes 127 + 5 calls · gin-examples 31 · gin-realworld 12 · express 31 · express-realworld 19 ·
fastify 6 + 1 call · nest 195 + 1 call (157 of them in the framework's own integration/ test apps) ·
eShop 23 + 6 calls · fastapi docs 84 + 11 calls · fastapi-template 19 · flask examples 12. Zero for
gorilla-mux (library only) and for jasontaylordev/CleanArchitecture (routes derived from method names
by convention — not extractable statically). Precision/recall per repo: docs/corpus-report.md.
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

CORPUS = {                                                    # pinned 2026-10-13
    "chi": ("go-chi/chi", "60755706125129a9f9dfb99ac22f7ba016a1b60c"),
    "fiber-recipes": ("gofiber/recipes", "1edaa79849f2fb70a39bfbad776f800ea69ace92"),
    "gin-examples": ("gin-gonic/examples", "439005e6e50c4abc65b0fd0a57aa88ce828cc9ee"),
    "gin-realworld": ("gothinkster/golang-gin-realworld-example-app", "626c372d259472148d93303f74aa9b9a1cdcef24"),
    "alertmanager": ("prometheus/alertmanager", "e3f6c51ddbfc527d2b040224f6b49b530da7a73d"),
    "gorilla-mux": ("gorilla/mux", "db9d1d0073d27a0a2d9a8c1bc52aa0af4374d265"),
    "nest": ("nestjs/nest", "fa152aff7ecdc6995f139a3a579f09c63b6aba22"),
    "express": ("expressjs/express", "a419aa7350389a275ab45fde2e849ed1f02449ef"),
    "express-realworld": ("gothinkster/node-express-realworld-example-app", "30b68e1e881462b2f4164ea09ab4c4f5699c7b0b"),
    "fastify": ("fastify/fastify", "e222f53aa267080b349eacdeaff03ea9a061e8c7"),
    "eshop": ("dotnet/eShop", "dc7ea499cd356924fb6689b3702964a5869dbae9"),
    "clean-arch-dotnet": ("jasontaylordev/CleanArchitecture", "bf7665ff37780713f68e61b892ba002c1504a696"),
    "fastapi": ("tiangolo/fastapi", "f5c6e9b4f9cadc1bf0f9a1fd672e621206b63007"),
    "fastapi-template": ("fastapi/full-stack-fastapi-template", "7257e606cb94eada1dca40173e2b7f99dd549bc6"),
    "flask": ("pallets/flask", "d086db856be187255b8ec61ef409357393020f32"),
}


def checkout(dest: Path, slug: str, sha: str) -> None:
    """Shallow clone of exactly `sha` (re-fetches when the pin changed)."""
    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(dest), *a], capture_output=True, text=True)
    if (dest / ".git").exists() and git("rev-parse", "HEAD").stdout.strip() == sha:
        return
    dest.mkdir(parents=True, exist_ok=True)
    git("init", "-q")
    # Retried: on a Docker Desktop bind mount the first fetch into a fresh repo fails with
    # "bad object <sha>" and the second one succeeds.
    for _ in range(3):
        r = git("fetch", "-q", "--depth", "1", f"https://github.com/{slug}.git", sha)
        if r.returncode == 0:
            break
    else:
        raise SystemExit(f"{dest.name}: could not fetch {slug}@{sha}: {r.stderr.strip()}")
    git("-c", "advice.detachedHead=false", "checkout", "-q", "-f", "FETCH_HEAD")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.environ.get("AIDD_CORPUS_DIR", str(Path.home() / ".cache/aidd-corpus/repos")))
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
        slug, sha = CORPUS[name]
        dest = base / name
        checkout(dest, slug, sha)
        repo = RepoInfo(tenant="corpus", name=name, ref="main", commit_sha=sha, root=str(dest))
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
                {"repo": slug, "sha": sha, "endpoints": [e.__dict__ for e in hr.endpoints], "calls": [c.__dict__ for c in hr.calls], "warnings": hr.warnings},
                indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
