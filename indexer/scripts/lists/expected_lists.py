#!/usr/bin/env python3
"""Edits the expected lists in `indexer/tests/corpus_expected/` and keeps their checked samples true to the corpus.
A list is written back in the order it was read, so one edit is one small diff. Plain Python 3, no Docker; it writes
the repository's files: the edit goes in its own commit, with the evidence (`file:line` at the pinned sha).

  expected_lists.py new NAME SHA [--spec FILE]            a list with no items, or the routes of an OpenAPI dump
  expected_lists.py add NAME KIND METHOD PATH [CATEGORY]  an expected item (KIND: endpoints or calls)
  expected_lists.py cat NAME KIND CATEGORY PATH_REGEX [METHOD]   the category of the items that match; `-` clears it
  expected_lists.py set NAME KEY=JSON ...                 top-level fields: source, scope, spec, notes
  expected_lists.py found RUN [NAME ...] [--apply]        categories of items the run now finds (no longer missed)
  expected_lists.py pending [NAME ...]                    checked items with no verdict, with their position
  expected_lists.py judge NAME KIND DEFAULT [N=VERDICT ...]   verdicts: ok, wrong or wrong:CATEGORY; DEFAULT `-` for none
  expected_lists.py sync RUN [NAME ...] [--apply]         checked items the run moved or lost
  expected_lists.py resample RUN NAME KIND [--apply]      the sample drawn again with the list's seed
  expected_lists.py sample RUN NAME [--n N] [--seed S] [--apply]   the first sample, for each kind the run has

RUN is a label under `$AIDD_CORPUS_HOME/runs` (default `~/.cache/aidd-corpus`). `found`, `sync`, `resample` and
`sample` only print what they would change until `--apply`.

`--holdout`, before the command, works on the hold-out's lists (`corpus_expected/holdout/`). `new` then needs the repo
pinned in HOLDOUT at that sha and unknown to the corpus. A list whose sample is fully judged is measured, and every
command but `pending` and `judge` refuses to open it."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lists_edit as E  # noqa: E402
import lists_holdout as HO  # noqa: E402
import lists_store as S  # noqa: E402
import lists_sync as Y  # noqa: E402


def _command(sub, cmd: str, *positional: str, apply: bool = False, spec: bool = False):
    """A subcommand; a positional ending in `?`, `*` or `+` takes that many values."""
    p = sub.add_parser(cmd)
    for arg in positional:
        name, nargs = (arg[:-1], arg[-1]) if arg[-1] in "?*+" else (arg, None)
        p.add_argument(name, nargs=nargs)
    if apply:
        p.add_argument("--apply", action="store_true")
    if spec:
        p.add_argument("--spec")
    return p


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="expected_lists.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--holdout", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    _command(sub, "new", "name", "sha", spec=True)
    _command(sub, "add", "name", "kind", "method", "path", "category?")
    _command(sub, "cat", "name", "kind", "category", "pattern", "method?")
    _command(sub, "set", "name", "pairs+")
    _command(sub, "pending", "names*")
    _command(sub, "judge", "name", "kind", "default", "overrides*")
    _command(sub, "found", "run", "names*", apply=True)
    _command(sub, "sync", "run", "names*", apply=True)
    _command(sub, "resample", "run", "name", "kind", apply=True)
    draw = _command(sub, "sample", "run", "name", apply=True)
    draw.add_argument("--n", type=int, default=20)
    draw.add_argument("--seed")
    return ap


def _line(name: str, kind: str, status: str, item: dict, then: dict | None = None) -> str:
    route = f"{item['method']} {item['path']}" + (f" -> {then['method']} {then['path']}" if then else "")
    return f"{name:16} {kind:9} {status:9} {route} {item.get('evidence', '')} ok={item.get('ok')} {item.get('category') or ''}"


def _open(a, name, lists):
    """A list to read or change; a measured hold-out's is not opened."""
    g = S.load(name, lists)
    if a.holdout:
        HO.check_open(name, g)
    return g


def cmd_new(a, lists, runs):
    if a.holdout:
        HO.check_new(a.name, a.sha)
    if (lists / f"{a.name}.json").exists():
        raise S.ListError(f"expected list '{a.name}' already exists")
    spec = json.loads(Path(a.spec).read_text()) if a.spec else None
    S.save(a.name, E.new_list(a.sha, spec), lists)
    print(f"wrote {lists / (a.name + '.json')}")
    return 0


def cmd_add(a, lists, runs):
    g = _open(a, a.name, lists)
    added = E.add_item(g, a.kind, a.method, a.path, a.category)
    S.save(a.name, g, lists)
    print("added" if added else "already there")
    return 0


def cmd_cat(a, lists, runs):
    g = _open(a, a.name, lists)
    count = E.set_category(g, a.kind, a.category, a.pattern, a.method)
    S.save(a.name, g, lists)
    print(f"{count} item(s)")
    return 0


def cmd_set(a, lists, runs):
    g = _open(a, a.name, lists)
    E.set_fields(g, a.pairs)
    S.save(a.name, g, lists)
    return 0


def cmd_pending(a, lists, runs):
    for name in a.names or S.names(lists):
        for kind, n, item in E.pending(S.load(name, lists)):
            print(f"{name:16} {kind:9} {n:4d} {item['method']} {item['path']} {item['evidence']} {item.get('raw') or ''}")
    return 0


def cmd_judge(a, lists, runs):
    g = S.load(a.name, lists)
    overrides = {int(n): v for n, _, v in (o.partition("=") for o in a.overrides)}
    count = E.judge(g, a.kind, a.default, overrides)
    S.save(a.name, g, lists)
    print(f"{count} verdict(s)")
    return 0


def cmd_found(a, lists, runs):
    for name in a.names or S.names(lists):
        run, g = S.load_run(a.run, name, runs), _open(a, name, lists)
        found = E.found_with_category(g, run) if run else []
        for kind, item in found:
            print(_line(name, kind, "found", item) + f" [{item['category']}]")
            if a.apply:
                item.pop("category")
        if a.apply and found:
            S.save(name, g, lists)
    return 0


def cmd_sync(a, lists, runs):
    for name in a.names or S.names(lists):
        g, run = _open(a, name, lists), S.load_run(a.run, name, runs)
        if not g.get("checked") or run is None:
            continue
        changes = Y.reconcile(g, run)
        for c in changes:
            print(_line(name, c.kind, c.status, c.old, c.new))
        if a.apply and changes:
            S.save(name, g, lists)
    return 0


def cmd_resample(a, lists, runs):
    g, run = _open(a, a.name, lists), S.load_run(a.run, a.name, runs)
    if run is None:
        raise Y.SyncError(f"no run '{a.run}' for '{a.name}'")
    for c in Y.resample(g, run, a.kind, a.name):
        print(_line(a.name, c.kind, c.status, c.old or c.new))
    if a.apply:
        S.save(a.name, g, lists)
    return 0


def cmd_sample(a, lists, runs):
    g, run = _open(a, a.name, lists), S.load_run(a.run, a.name, runs)
    if run is None:
        raise Y.SyncError(f"no run '{a.run}' for '{a.name}'")
    for kind in Y.draw(g, run, a.name, a.n, a.seed):
        items = g["checked"][kind]
        right = sum(i["ok"] is True for i in items)
        print(f"{a.name} {kind}: {len(items)} drawn, {right} match the list, {len(items) - right} to judge")
    if a.apply:
        S.save(a.name, g, lists)
    return 0


HANDLERS = {"new": cmd_new, "add": cmd_add, "cat": cmd_cat, "set": cmd_set, "pending": cmd_pending, "judge": cmd_judge,
            "found": cmd_found, "sync": cmd_sync, "resample": cmd_resample, "sample": cmd_sample}


def main(argv: list[str], lists: Path = S.LISTS, runs: Path = S.RUNS) -> int:
    args = parser().parse_args(argv)
    if args.holdout:
        lists = lists / "holdout"
    try:
        return HANDLERS[args.cmd](args, lists, runs)
    except (S.ListError, E.VerdictError, Y.SyncError) as e:
        print(f"expected_lists: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
