"""TS's and JS's `EXTENDS`, `IMPLEMENTS` and `OVERRIDES`. A type's edges are the declarations TypeScript's own checker
resolves its heritage clauses to (scripts/checks/ts_heritage.js, which reads and types the files): what `implements`
names is implemented, a class or not, and what `extends` names extended. An override is what JS runs on an instance of
each class of the case (scripts/checks/ts_runs.js, which compiles the case's own files and runs them): for each method
a class above it declares, the implementation of the class whose prototype holds the name, none where the instance
holds the name itself or an accessor does."""

import contextlib
import io
import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest

CHECKS = Path(__file__).resolve().parents[1] / "scripts" / "checks"
FILES = {
    "package.json": '{"name": "app"}\n',
    "app/models.ts": """export interface Saver { save(): string; }
export interface Store extends Saver { load(): string; save(): string; }
export abstract class Base implements Saver {
  constructor() {}
  abstract save(): string;
  load() { return "Base"; }
  find(a: string): string;
  find(a: number): string;
  find(a: any) { return "Base"; }
  static create() { return "Base"; }
  get size() { return 0; }
  get(key: string) { return "Base"; }
}
export class Plain { save() { return "Plain"; } }
export default class Root { run() { return "Root"; } }
export class Holder<T> { put(x: T) {} }
""",
    "app/index.ts": 'export * from "./models";\nexport { default as Root } from "./models";\n',
    "app/use.ts": """import { Base, Holder, Root as R, Store } from "./index";
import * as m from "./models";
import { Plain as P } from "./models";

export class Doc extends Base implements Store {
  constructor() { super(); }
  save() { return "Doc"; }
  find(a: string): string;
  find(a: any) { return "Doc"; }
  create() { return "Doc"; }
  get size() { return 1; }
  get(key: string) { return "Doc"; }
}
export class Note extends Doc {
  load() { return "Note"; }
  static create() { return "Note"; }
}
export class Draft extends m.Base {
  save() { return "Draft"; }
  load = () => "Draft";
}
export class Redraft extends Draft { load() { return "Redraft"; } }
export class Shown extends Base {
  save() { return "Shown"; }
  get load() { return () => "Shown"; }
}
export class Reshown extends Shown { load() { return "Reshown"; } }
export class Sized extends Base {
  save() { return "Sized"; }
  size() { return 2; }
}
export abstract class Mid extends P { abstract save(): string; }
export class Low extends Mid {}
export class Leaf extends R { run() { return "Leaf"; } }
export class Copy implements P { save() { return "Copy"; } }
export class Names extends Holder<string> { put(x: string) {} }
export class Field0 { run = () => "Field0"; }
export class Field1 extends Field0 { run() { return "Field1"; } }
export abstract class Req { abstract request(): string; }
export class ReqImpl extends Req { request = () => "ReqImpl"; }
const other = () => "other";
export class Keeps { run() { return "Keeps"; } }
export class Refs extends Keeps { run = other; }
export class Statics { static make = () => 1; }
export class Statics2 extends Statics { static make = () => 2; }
export class Shadow0 { run = function () { return "Shadow0"; }; }
export class Shadow1 extends Shadow0 { run() { return "Shadow1"; } }
export class Shadow2 extends Shadow1 { run = () => "Shadow2"; }
function mixin<T extends new (...a: any[]) => object>(B: T) { return class extends B {}; }
export class Mixed extends mixin(P) { save() { return "Mixed"; } }
""",
    "app/widget.tsx": 'import { Doc } from "./use";\nexport class Widget extends Doc { save() { return "Widget"; } }\n',
    "app/legacy.js": """const { Base } = require("./models");
class Old extends Base { save() { return "Old"; } }
class Fld extends Base { save() { return "Fld"; } load = () => "Fld"; }
module.exports = { Old, Fld };
""",
    "app/view.ts": 'import { Component } from "some-package";\nexport class View extends Component { render() {} }\n',
}


def _node(script: str, *args: str, stdin: str | None = None) -> list[dict]:
    out = subprocess.run(["node", str(CHECKS / script), *args], input=stdin, capture_output=True, text=True, check=True,
                         env={**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}).stdout
    return [json.loads(line) for line in out.splitlines()]


@pytest.fixture(scope="module")
def case(tmp_path_factory):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    root = tmp_path_factory.mktemp("ts-hierarchy")
    for rel, body in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)),
                                      convs=[])
    return root, res, rv, _node("ts_heritage.js", "--members", str(root))


def _checker_edges(rows: list[dict]) -> set[tuple[str, str, str]]:
    return {(f"{_module(r['file'])}:{r['name']}", "IMPLEMENTS" if r["clause"] == "implements" else "EXTENDS", d)
            for r in rows if "clause" in r for d in r["declared"] if d != "outside"}


def _module(file: str) -> str:
    return str(Path(file).with_suffix(""))


def test_a_types_edges_are_the_declarations_the_checker_resolves_its_clauses_to(case):
    _, res, rv, rows = case
    q = {s.id: s.qualified_name for s in res.symbols}
    edges = {(q[e.source_id], e.kind, q[e.target_id]) for e in rv.hierarchy if e.kind != "OVERRIDES"}
    assert edges == _checker_edges(rows)
    assert ("app/use:Copy", "IMPLEMENTS", "app/models:Plain") in edges
    assert ("app/legacy:Old", "EXTENDS", "app/models:Base") in edges
    assert not any(s in ("app/use:Mixed", "app/view:View") for s, _, _ in edges)


def test_an_override_is_what_js_runs_on_an_instance_of_each_class(case):
    root, res, rv, rows = case
    by_id = {s.id: s for s in res.symbols}
    edges = {((by_id[e.source_id].qualified_name, by_id[e.source_id].line_start),
              (by_id[e.target_id].qualified_name, by_id[e.target_id].line_start), e.receivers)
             for e in rv.hierarchy if e.kind == "OVERRIDES"}
    assert edges == _overrides(rows, _node("ts_runs.js", str(root)))
    doc = ("app/use:Doc", "app/use:Note", "app/widget:Widget")
    assert (("app/use:Doc.find", 9), ("app/models:Base.find", 7), doc) in edges


def _overrides(rows: list[dict], ran: list[dict]) -> set:
    """For each class the case ran and each method a type above it declares, the implementation of the class whose
    prototype holds the name, with the types below the method's a receiver of which may hold such an instance."""
    up: dict[str, set[str]] = defaultdict(set)
    for source, _, target in _checker_edges(rows):
        up[source].add(target)
    members = defaultdict(list)
    for r in (r for r in rows if "member" in r):
        members[f"{_module(r['file'])}:{r['name']}"].append(r)
    extends = {source: target for source, kind, target in _checker_edges(rows) if kind == "EXTENDS"}
    found = defaultdict(set)
    for r in ran:
        runs, impl = _implementation(members, extends, r)
        if runs is None:
            continue
        for owner in _above(up, r["class"]):
            for o in (o for o in members[owner] if o["member"] == r["name"] and (o["form"] in METHODS or o.get("fn"))):
                if runs != owner:
                    key = (f"{runs}.{r['name']}", impl), (f"{owner}.{r['name']}", o["line"]), owner
                    found[key].add(r["class"])
    return {(source, target, tuple(sorted({t for d in ds for t in _above(up, d) | {d} if owner in _above(up, t)})))
            for (source, target, owner), ds in found.items()}


METHODS = ("method", "signature", "abstract")


def _implementation(members: dict, extends: dict[str, str], r: dict) -> tuple[str | None, int]:
    """The class that runs the name on an instance of `r`'s class and the line of what it declares: its method, or the
    function the field of the nearest class that holds the name holds, which an instance holds as its own."""
    if r["runs"] in (None, "accessor", "outside"):
        return None, 0
    if r["runs"] != "own":
        impl = max((m for m in members[r["runs"]] if m["member"] == r["name"] and m["form"] == "method"),
                   key=lambda m: m["line"])
        return r["runs"], impl["line"]
    holder: str | None = r["class"]
    while holder is not None:
        fields = [m for m in members[holder] if m["member"] == r["name"] and m["form"] == "field"]
        if fields:
            return (holder, fields[-1]["line"]) if fields[-1].get("fn") else (None, 0)
        holder = extends.get(holder)
    return None, 0


def _above(up: dict[str, set[str]], t: str) -> set[str]:
    seen, todo = set(), list(up.get(t, ()))
    while todo:
        if (b := todo.pop()) not in seen:
            seen.add(b)
            todo += up.get(b, ())
    return seen


def test_the_closure_of_a_types_edges_is_the_ancestry_the_resolver_walks(case):
    from aidd_indexer import languages
    from aidd_indexer.core.resolve import TYPE_KINDS, Resolver
    from aidd_indexer.cli import extract_tree
    from aidd_indexer.core.model import RepoInfo
    root, res, rv, _ = case
    with contextlib.redirect_stderr(io.StringIO()):
        tree, extractors = extract_tree(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)))
        resolver = Resolver(tree, extractors)
        resolver.run()
    q = {s.id: s.qualified_name for s in res.symbols}
    up: dict[str, set[str]] = defaultdict(set)
    for e in (e for e in rv.hierarchy if e.kind != "OVERRIDES"):
        up[q[e.source_id]].add(q[e.target_id])
    ts = languages.by_id("typescript")
    for t in {s.qualified_name for s in res.symbols if s.kind in TYPE_KINDS}:
        assert _above(up, t) == set(ts.supertypes(resolver.ctx, t)), t


def test_an_abstract_method_is_a_method_of_its_class(case):
    _, res, _, _ = case
    assert [(s.kind, s.line_start, s.signature) for s in res.symbols if s.qualified_name == "app/models:Base.save"] \
        == [("method", 5, "abstract save(): string")]
