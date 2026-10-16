#!/usr/bin/env python3
"""Calibration corpus for the HTTP integration extractor (aidd_indexer/core/integrations.py + languages/<lang>/http.py).

Clones public repositories across Go / TypeScript / C# / Python frameworks and prints, per
repo, how many routes and outbound calls the extractor finds — a regression check that the
heuristics do not drift towards one team's style. Needs network + the grammars cached
(run inside the indexer image, or with TREE_SITTER_LANGUAGE_PACK_CACHE_DIR set).

    python scripts/http_corpus.py [--dir ~/.cache/aidd-corpus/repos] [--json out/] [repo-name ...]
        [--baseline runs/<earlier>/]   # per repo: ids (method path_key evidence) removed/added, handler changes
        [--expected [dir]]             # precision/recall against tests/corpus_expected/<repo>.json
        [--sample N [--seed S]]        # N routes + N calls per repo, reproducible, to check by hand
        [--show K]                     # list up to K items behind each number (default 10, 0 = none)
        [--reuse runs/<earlier>/]      # score that saved run instead of extracting (editing gabaritos only)

The measuring is in `corpus_metrics.py` (gabarito format, matching rules).

Every repo is pinned to a commit (`CORPUS`: name -> (slug, sha)) so a run is comparable with an
earlier one; bump a sha deliberately and re-run the baseline in the same change. Clones live outside
the repository (`--dir`, or `AIDD_CORPUS_DIR`) and are never versioned.

Baseline at the pinned commits (2026-10-16, v2 after H2b mount graph step 2, routes + calls): Go — alertmanager 21 · chi 50 ·
fiber-recipes 164+6 · gin-examples 40+1 · gin-realworld 20 · gorilla-mux 0 (library only) · gitea 1143+4 ·
mattermost 690+42 · kratos 80+15 · argo-cd 17+104 · gotify 48+28 · go-feature-flag 18+4 · go-kit-examples 16.
TS/JS — express 32 · express-realworld 20 · fastify 8+1 · nest 195+1 (157 in the framework's own test apps) ·
immich 295+7 · nodebb 90+185 · ghost 311+30 · express-boilerplate 8 · fastify-demo 10 · hono-examples 27 ·
taxonomy 0+6 (Next.js file routes). C# — eshop 30+24 · clean-arch-dotnet 1 · eshop-on-web 33+7 · eshop-support
18+19 · ardalis-clean-arch 19 · jellyfin 422+13 · bitwarden 671+30 · notifo 130+218 · rapid-blazor 18+17 ·
azure-saas 35+26 (the last three with NSwag clients). Python — fastapi 87+9 ·
fastapi-template 23 · flask 18 · zulip 0+20 and netbox 0 (Django) · dispatch 290+288 · aiohttp-demos 24+1 ·
ctfd 122+79. Whole run ~11 min in Docker (mattermost ~3 min, bitwarden ~2 min); grafana is out (memory, see
CORPUS). Precision/recall per repo and the ranking of gaps: docs/corpus-report.md.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_metrics as M  # noqa: E402

EXPECTED_DIR = Path(__file__).resolve().parents[1] / "tests" / "corpus_expected"

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
    # H2b (pinned 2026-10-15): real apps and services, preferring a committed spec
    "gitea": ("go-gitea/gitea", "1c117a9352e4a64cd301028403c33949ab146424"),
    "gotify": ("gotify/server", "64f28352dce6e8a95c0a24b54daabedd66aef669"),
    "kratos": ("ory/kratos", "b86338da04a040247a07f46100a86dcfb3875909"),
    "go-kit-examples": ("go-kit/examples", "e18c82edc2f9c7de3aff9748751d63270c052c1b"),
    "go-feature-flag": ("thomaspoignant/go-feature-flag", "d7cbdbf6689be02f036e2ecce3199df5e41142ea"),
    "argo-cd": ("argoproj/argo-cd", "ced5c83bb75398eb1d4792505802f3d788597a18"),
    "mattermost": ("mattermost/mattermost", "4b32c6f092d84602989d78a5eda768d2b1856c76"),
    # grafana/grafana@044dd4f9 was a candidate (Group closures + committed spec): the whole-repo extraction
    # (24k files) is killed for memory at 7.7 GB in Docker Desktop — out until the indexer scales (H2b log).
    "immich": ("immich-app/immich", "c43573bb2e657aaecc403c385038ae4b1bbdc86f"),
    "nodebb": ("NodeBB/NodeBB", "4408f117031bfd13451b57989a46771b3ff735f2"),
    "ghost": ("TryGhost/Ghost", "848c7323c82c502717527b864858c7235b276da9"),
    "express-boilerplate": ("hagopj13/node-express-boilerplate", "179ae84efec61b14206d0305d941daed6c6d07f9"),
    "fastify-demo": ("fastify/demo", "5cd560125b3c2f0d42192bc7f493e8e3b9e75e52"),
    "hono-examples": ("honojs/examples", "3b0b62875a0e1265763fea1c6388866d5697ef81"),
    "taxonomy": ("shadcn-ui/taxonomy", "298a8857c7128a0d121e7f699dfd729f23b3966d"),
    "eshop-on-web": ("dotnet-architecture/eShopOnWeb", "4da8212117e87d808d4bbc7da6286fd2147ce606"),
    "eshop-support": ("dotnet/eShopSupport", "1a772ff84f750167c020fc8b678b7433290ba783"),
    "ardalis-clean-arch": ("ardalis/CleanArchitecture", "e7c79be54ba0b001a5b332c1efe935f520b9db4b"),
    "jellyfin": ("jellyfin/jellyfin", "aec42b345e1a7da25ee5492183f12209338df688"),
    "bitwarden": ("bitwarden/server", "e625db923ca2cc62542de17c59738ca638ccfa5d"),
    "zulip": ("zulip/zulip", "7eed14f6166b53c10228900be047387346f95414"),
    "netbox": ("netbox-community/netbox", "9a9770995d2e11476e10bbf364a64c57b668439e"),
    "dispatch": ("Netflix/dispatch", "dd2837e82a0bf5565b1b4b4b91ea30b7262d4061"),
    "aiohttp-demos": ("aio-libs/aiohttp-demos", "411ddddd09b6934d1d87eb0fcf9383e7fa104bc0"),
    "ctfd": ("CTFd/CTFd", "6b01b531e8445c781a8bdcdc9409400e19207037"),
    # .NET with NSwag-generated clients (H2b item 7; pinned 2026-10-16)
    "notifo": ("notifo-io/notifo", "54da324ff6f4c51ca959751bdc6572e20c10a6e4"),
    "rapid-blazor": ("jasontaylordev/RapidBlazor", "923b6d4537d7c8b499435c7378f4bd8ee69b2271"),
    "azure-saas": ("Azure/azure-saas", "80ac009ec7b7738ab7861ea64af8de01435638de"),
}


LANGUAGE = {"chi": "Go", "fiber-recipes": "Go", "gin-examples": "Go", "gin-realworld": "Go", "alertmanager": "Go", "gorilla-mux": "Go",
            "nest": "TS/JS", "express": "TS/JS", "express-realworld": "TS/JS", "fastify": "TS/JS",
            "eshop": "C#", "clean-arch-dotnet": "C#", "fastapi": "Python", "fastapi-template": "Python", "flask": "Python",
            "gitea": "Go", "gotify": "Go", "kratos": "Go", "go-kit-examples": "Go", "go-feature-flag": "Go", "argo-cd": "Go",
            "mattermost": "Go",
            "immich": "TS/JS", "nodebb": "TS/JS", "ghost": "TS/JS", "express-boilerplate": "TS/JS", "fastify-demo": "TS/JS",
            "hono-examples": "TS/JS", "taxonomy": "TS/JS",
            "eshop-on-web": "C#", "eshop-support": "C#", "ardalis-clean-arch": "C#", "jellyfin": "C#", "bitwarden": "C#",
            "notifo": "C#", "rapid-blazor": "C#", "azure-saas": "C#",
            "zulip": "Python", "netbox": "Python", "dispatch": "Python", "aiohttp-demos": "Python", "ctfd": "Python"}


EXT_LANGUAGE = {".go": "Go", ".cs": "C#", ".py": "Python",
                **{e: "TS/JS" for e in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte")}}


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


def _pct(v: float | None) -> str:
    return "  —  " if v is None else f"{v:5.1%}"


def _items(label: str, rows: list, show: int) -> None:
    for r in rows[:show]:
        print(f"      {label} {' '.join(map(str, r)) if isinstance(r, tuple) else r}")
    if len(rows) > show > 0:
        print(f"      … {len(rows) - show} more")


def report_baseline(name: str, run: dict, baseline: Path, show: int) -> bool:
    f = baseline / f"{name}.json"
    if not f.exists():
        print(f"  baseline: none for {name}")
        return True
    old = json.loads(f.read_text())
    if old.get("sha") and old["sha"] != run["sha"]:
        print(f"  baseline: taken at {old['sha'][:10]}, run at {run['sha'][:10]} — ids may differ for that reason alone")
    diffs = {k: M.diff_runs(old, run, k) for k in M.KINDS}
    if not any(diffs.values()):
        print("  baseline: identical")
        return False
    print("  baseline: " + " | ".join(f"{k} -{len(d.removed)} +{len(d.added)} ~{len(d.resolution)}" for k, d in diffs.items()))
    for k, d in diffs.items():
        _items(f"{k} -", d.removed, show)
        _items(f"{k} +", d.added, show)
        _items(f"{k} ~{M.SECONDARY[k]}", d.resolution, show)
    return True


CATEGORIES: dict[tuple[str, str], collections.Counter] = collections.defaultdict(collections.Counter)
CATEGORY_REPOS: dict[tuple[str, str], set[str]] = collections.defaultdict(set)   # breadth, so one big repo does not rank alone
POOLED: dict[str, dict[str, collections.Counter]] = collections.defaultdict(lambda: {k: collections.Counter() for k in M.KINDS})


def report_expected(name: str, run: dict, expected: Path, show: int) -> dict | None:
    f = expected / f"{name}.json"
    if not f.exists():
        return None
    gab = json.loads(f.read_text())
    if gab.get("sha") and gab["sha"] != run["sha"]:
        print(f"  expected: gabarito read at {gab['sha'][:10]}, run at {run['sha'][:10]} — re-check it before trusting P/R")
    out = {}
    langs = gab.get("language") or {}              # a kind written in another language than the repo's (a UI's calls)
    for k in M.KINDS:
        sc, ck = M.score(run, gab, k), M.checked_precision(run, gab, k)
        if sc is not None:
            src = gab.get("source", "?")
            print(f"  expected {k:9} ({src.get(k, '?') if isinstance(src, dict) else src}): P {_pct(sc.precision)} R {_pct(sc.recall)} "
                  f"| extracted {sc.extracted} expected {sc.expected} fp {len(sc.false_positives)} fn {len(sc.false_negatives)}")
            _items("fp", sc.false_positives, show)
            misses = M.miss_categories(gab, k, sc)
            _items("fn", [f"{m} {p}" + (f" [{c}]" if c else "") for (m, p), c in misses.items()], show)
            for c in misses.values():
                CATEGORIES[(k, c or "uncategorized")]["fn"] += 1
                CATEGORY_REPOS[(k, c or "uncategorized")].add(name)
        if ck is not None:
            print(f"  checked  {k:9}: P {_pct(ck.precision)} ({ck.ok}/{ck.judged}, {ck.pending} pending, {len(ck.stale)} stale)")
            _items("wrong", [f"{i['evidence']} {i['method']} {i['path']} [{i.get('category')}]" for i in ck.wrong], show)
            for i in ck.wrong:
                CATEGORIES[(k, i.get("category") or "uncategorized")]["wrong"] += 1
                CATEGORY_REPOS[(k, i.get("category") or "uncategorized")].add(name)
            _items("stale", [f"{i['evidence']} {i['method']} {i['path']}" for i in ck.stale], show)
        if sc is not None:
            POOLED[langs.get(k) or LANGUAGE.get(name, "?")][k].update(
                extracted=sc.extracted, tp_x=sc.extracted - len(sc.false_positives),
                expected=sc.expected, tp_e=sc.expected - len(sc.false_negatives))
        if ck is not None:                          # each sampled item counts for the language of its own file
            for i in (gab.get("checked") or {}).get(k, []):
                if i.get("ok") is not None:
                    lang = EXT_LANGUAGE.get(Path(M.evidence_file(i["evidence"])).suffix, LANGUAGE.get(name, "?"))
                    POOLED[lang][k].update(judged=1, ok=int(i["ok"]))
        out[k] = (sc, ck)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.environ.get("AIDD_CORPUS_DIR", str(Path.home() / ".cache/aidd-corpus/repos")))
    ap.add_argument("--json", default=None, help="directory to dump per-repo candidates as JSON")
    ap.add_argument("--baseline", type=Path, default=None, help="directory of an earlier --json run to diff against")
    ap.add_argument("--reuse", type=Path, default=None,
                    help="score a saved --json run (same pinned sha) instead of extracting again — for editing gabaritos, "
                         "never for measuring an extractor change")
    ap.add_argument("--expected", type=Path, nargs="?", const=EXPECTED_DIR, default=None,
                    help=f"gabarito directory (default {EXPECTED_DIR.relative_to(Path(__file__).resolve().parents[1])})")
    ap.add_argument("--sample", type=int, default=0, help="print N sampled routes and N calls per repo")
    ap.add_argument("--seed", default="0")
    ap.add_argument("--show", type=int, default=10)
    ap.add_argument("repos", nargs="*")
    args = ap.parse_args()
    os.environ.setdefault("AIDD_TENANT", "corpus")
    from aidd_indexer.cli import extract_tree
    from aidd_indexer.core.integrations import extract_http
    from aidd_indexer.core.model import RepoInfo

    base = Path(args.dir)
    base.mkdir(parents=True, exist_ok=True)
    changed, measured = [], {}
    for name in args.repos or sorted(CORPUS):
        slug, sha = CORPUS[name]
        saved = args.reuse / f"{name}.json" if args.reuse else None
        if saved and saved.exists() and json.loads(saved.read_text()).get("sha") == sha:
            run = json.loads(saved.read_text())
            print(f"{name:20} reused {args.reuse} | routes {len(run['endpoints']):4} | calls {len(run['calls']):4}")
        else:
            dest = base / name
            checkout(dest, slug, sha)
            repo = RepoInfo(tenant="corpus", name=name, ref="main", commit_sha=sha, root=str(dest))
            t0 = time.time()
            with contextlib.redirect_stderr(io.StringIO()):
                res, extractors = extract_tree(repo)
                t1 = time.time()
                hr = extract_http(repo, extractors, modules=res.modules)
            fw = collections.Counter(e.framework for e in hr.endpoints)
            via = collections.Counter(c.via.split(".")[-1] for c in hr.calls)
            with_handler = sum(1 for e in hr.endpoints if e.handler_id)
            print(f"{name:20} {len(res.files):5} files | routes {len(hr.endpoints):4} (handler {with_handler:4}) {dict(fw)} "
                  f"| calls {len(hr.calls):4} {dict(via.most_common(5))} | warn {len(hr.warnings)} | {time.time()-t0:.1f}s"
                  f" (http {time.time()-t1:.1f}s)")
            run = {"repo": slug, "sha": sha, "endpoints": [e.__dict__ for e in hr.endpoints], "calls": [c.__dict__ for c in hr.calls],
                   "warnings": hr.warnings}
        if args.json:
            Path(args.json).mkdir(parents=True, exist_ok=True)
            (Path(args.json) / f"{name}.json").write_text(json.dumps(run, indent=1, default=str))
        if args.baseline and report_baseline(name, run, args.baseline, args.show):
            changed.append(name)
        if args.expected and (m := report_expected(name, run, args.expected, args.show)):
            measured[name] = m
        if args.sample:
            for k in M.KINDS:
                picked = M.sample(run, k, args.sample, args.seed, name)
                if picked:
                    print(f"  sample {k} (seed {args.seed}):")
                    for item in picked:
                        print("    " + json.dumps(item, ensure_ascii=False) + ",")
    if args.baseline:
        print(f"\nbaseline {args.baseline}: {len(changed)} repo(s) differ" + (f" — {', '.join(changed)}" if changed else ""))
    if args.expected:
        print(f"\nexpected {args.expected}: {len(measured)} repo(s) with a gabarito" + (f" — {', '.join(measured)}" if measured else ""))
        if POOLED:
            ratio = lambda a, b: _pct(a / b if b else None)
            print(f"\n{'language':8} {'kind':10} {'P checked':>16} {'P gabarito':>16} {'R gabarito':>16}")
            for lang, kinds in sorted(POOLED.items()):
                for k, c in kinds.items():
                    if c:
                        print(f"{lang:8} {k:10} {ratio(c['ok'], c['judged'])} {c['ok']:>4}/{c['judged']:<4} "
                              f"{ratio(c['tp_x'], c['extracted'])} {c['tp_x']:>4}/{c['extracted']:<4} "
                              f"{ratio(c['tp_e'], c['expected'])} {c['tp_e']:>4}/{c['expected']:<4}")
        if CATEGORIES:
            print(f"\n{'kind':10} {'category':28} {'wrong':>5} {'fn':>4} {'repos':>5}   (wrong: checked items judged wrong · "
                  "fn: distinct expected pairs missed · repos: where it shows up)")
            for (k, c), n in sorted(CATEGORIES.items(), key=lambda kv: (kv[0][0], -(kv[1]["wrong"] + kv[1]["fn"]), kv[0][1])):
                print(f"{k:10} {c:28} {n['wrong']:5} {n['fn']:4} {len(CATEGORY_REPOS[(k, c)]):5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
