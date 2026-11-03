"""A member an interface, or the object type a type alias names, declares as a property whose type is a function type
(`push: (x: number) => void`) is a `method` symbol of its owner, as a method signature is: the declaration TypeScript's
own checker resolves a call of it to (scripts/checks/ts_checker.js), which reads and types the files and runs nothing,
with the member's first line as its signature, an optional, a `readonly` and a generic one too, and through an
interface that extends its owner. A class that implements the interface with a method, or with a field that holds a
function, overrides it as it overrides the interface's method signature: there the reference is what JS runs on an
instance, which the hierarchy's overrides follow, not the compiler. A member the syntax does not give as a function has no symbol: a
data property, a constructor type, a name written as a string or computed, a member of an object type no declaration
names, and anything of a JS file, which declares types in comments only. A member whose function type a name, `typeof`
or a union gives, and one of an object literal, are debts (test_ts_debts.py)."""

import contextlib
import io
import json
import os
import subprocess
from pathlib import Path

import pytest

from aidd_indexer.cli import extract_and_resolve
from aidd_indexer.core.model import RepoInfo

CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "checks" / "ts_checker.js"
MODELS = """export interface Api {
  push: (x: number) => void;
  stop?: () => void;
  readonly now: () => number;
  get: <T>(key: string) => T;
  send(x: number): void;
}
export interface Child extends Api {
  more: () => void;
}
export type Handlers = {
  run: () => void;
  done?: (e: Error) => void;
};
export type Pair<T> = { take: (t: T) => void };
const KEY = "key";
export interface Rest {
  name: string;
  ctor: new () => Api;
  "quoted": () => void;
  [KEY]: () => void;
}
export type Either = { left: () => void } | { right: () => void };
export type Both = { first: () => void } & { second: () => void };
export function take(o: { go: () => void }) { return o.go(); }
"""
IMPL = """import { Api } from "./models";
export class ByMethod implements Api {
  push(x: number) {}
  now() { return 1; }
  get<T>(key: string): T { return key as T; }
  send(x: number) {}
}
export class ByField implements Api {
  push = (x: number) => {};
  now = () => 1;
  get = <T>(key: string): T => key as T;
  send = (x: number) => {};
}
"""
PLAIN = """/** @typedef {{ jsRun: () => void }} JsHandlers */
/** @param {JsHandlers} h */
export function main(h) { return h.jsRun(); }
"""
# receiver, method, how it is called, the member the call reaches, its signature
CALLS = [
    ("api", "push", "(1)", "app/models:Api.push", "push: (x: number) => void"),
    ("api", "stop", "?.()", "app/models:Api.stop", "stop?: () => void"),
    ("api", "now", "()", "app/models:Api.now", "readonly now: () => number"),
    ("api", "get", '<string>("k")', "app/models:Api.get", "get: <T>(key: string) => T"),
    ("child", "push", "(2)", "app/models:Api.push", "push: (x: number) => void"),
    ("child", "more", "()", "app/models:Child.more", "more: () => void"),
    ("h", "run", "()", "app/models:Handlers.run", "run: () => void"),
    ("h", "done", '?.(new Error("e"))', "app/models:Handlers.done", "done?: (e: Error) => void"),
    ("p", "take", "(1)", "app/models:Pair.take", "take: (t: T) => void"),
]
USE = ('import { Api, Child, Handlers, Pair } from "./models";\n'
       "export function main(api: Api, child: Child, h: Handlers, p: Pair<number>) {\n"
       + "".join(f"  {receiver}.{method}{args};\n" for receiver, method, args, _, _ in CALLS) + "}\n")
FIRST_CALL = 3
FILES = {"package.json": '{"name": "app"}\n', "app/models.ts": MODELS, "app/impl.ts": IMPL, "app/use.ts": USE,
         "app/plain.js": PLAIN}
# the file, and what the line of a member that is no symbol writes
NOT_A_FUNCTION = {
    "a-data-property": ("app/models.ts", "name: string"),
    "a-constructor-type": ("app/models.ts", "ctor: new"),
    "a-name-written-as-a-string": ("app/models.ts", '"quoted"'),
    "a-computed-name": ("app/models.ts", "[KEY]"),
    "a-member-of-a-parameters-object-type": ("app/models.ts", "go: ()"),
    "a-member-of-a-union-of-object-types": ("app/models.ts", "left: ()"),
    "a-member-of-an-intersection-of-object-types": ("app/models.ts", "first: ()"),
    "a-member-a-js-comment-declares": ("app/plain.js", "jsRun: ()"),
}


@pytest.fixture(scope="module")
def case(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    for rel, body in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    return root


@pytest.fixture(scope="module")
def checked(case) -> dict[int, tuple[str, ...]]:
    """What the checker resolves each call of app/use.ts to, by line."""
    out = subprocess.run(["node", str(CHECKER), str(case)], capture_output=True, text=True, check=True,
                         env={**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}).stdout
    return {r["line"]: tuple(r["declared"]) for r in map(json.loads, out.splitlines()) if r["file"] == "app/use.ts"}


@pytest.fixture(scope="module")
def indexed(case):
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(case)),
                                   convs=[])


def test_the_checker_resolves_each_call_to_the_member_the_case_names(checked):
    assert checked == {FIRST_CALL + i: (member,) for i, (_, _, _, member, _) in enumerate(CALLS)}


def test_a_function_member_is_the_method_the_checker_resolves_its_call_to(checked, indexed):
    res, _ = indexed
    found = {s.qualified_name: (s.kind, s.signature) for s in res.symbols}
    signatures = {member: signature for _, _, _, member, signature in CALLS}
    declared = {d for ds in checked.values() for d in ds}
    assert {d: found.get(d) for d in declared} == {d: ("method", signatures[d]) for d in declared}


def test_a_class_overrides_a_function_member_as_it_overrides_a_method_signature(indexed):
    res, rv = indexed
    q = {s.id: s.qualified_name for s in res.symbols}
    overrides = {(q[e.source_id], q[e.target_id]) for e in rv.hierarchy if e.kind == "OVERRIDES"}
    assert overrides == {(f"app/impl:{c}.{m}", f"app/models:Api.{m}") for c in ("ByMethod", "ByField")
                         for m in ("push", "now", "get", "send")}


@pytest.mark.parametrize("file, written", [pytest.param(*v, id=k) for k, v in NOT_A_FUNCTION.items()])
def test_a_member_the_syntax_does_not_give_as_a_function_has_no_symbol(indexed, file, written):
    res, _ = indexed
    line = next(i for i, text in enumerate(FILES[file].splitlines(), 1) if written in text)
    path = {f.id: f.path for f in res.files}
    assert [s.qualified_name for s in res.symbols
            if s.kind == "method" and path[s.file_id] == file and s.line_start == line] == []
