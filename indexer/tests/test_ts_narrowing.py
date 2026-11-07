"""A value a function tests with `instanceof` may be narrowed by the flow to a class its declaration does not name, where
TypeScript's checker resolves a call on it to the class's method. The index does not follow the flow, so the receiver of
such a call has no type and the call goes by name, as in the version before types; a call on a value no function of the
file tests, or one it tests under another name, is typed. Every case is checked against the declarations the checker
resolves the call to (scripts/checks/ts_checker.js)."""

import contextlib
import io
import json
import os
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

from aidd_indexer.languages.typescript.receivers import NARROWED

CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "checks" / "ts_checker.js"
PING = "app/models:Target.ping"
IMPORT = 'import { Crate, Grid, Holder, Target, Wrapper } from "./models";\n'


class Case(NamedTuple):
    use: str                        # the source of the file, which makes one call of `method`
    declared: str                   # what the checker resolves the call to
    answer: str                     # typed: one edge by the type; by-name: the edges by name reach `declared`
    method: str


MODELS = ("export interface Target { id: string; ping(): void }\n"
          "export class Grid implements Target { id = ''; ping() {} stopA() {} stopB() {} stopC() {} stopD() {} }\n"
          "export interface Holder { target: Target }\n"
          "export interface Wrapper { inner: Target }\n"
          "export class Crate implements Wrapper { inner = new Grid(); }\n")
USES = {
    "app/negated.ts": Case(IMPORT + "export function main(t: Target) {\n  if (!(t instanceof Grid)) return;\n"
                           "  t.stopA();\n}\n", "app/models:Grid.stopA", "by-name", "stopA"),
    "app/member.ts": Case(IMPORT + "export function main(h: Holder) {\n  if (h.target instanceof Grid) {\n"
                          "    h.target.stopB();\n  }\n}\n", "app/models:Grid.stopB", "by-name", "stopB"),
    "app/field.ts": Case(IMPORT + "export class Keeper {\n  private t: Target | null = null;\n  run() {\n"
                         "    if (this.t && this.t instanceof Grid) {\n      this.t.stopC();\n    }\n  }\n}\n",
                         "app/models:Grid.stopC", "by-name", "stopC"),
    "app/chain.ts": Case(IMPORT + "export function main(w: Wrapper) {\n  if (w instanceof Crate) {\n"
                         "    w.inner.stopD();\n  }\n}\n", "app/models:Grid.stopD", "by-name", "stopD"),
    "app/untested.ts": Case(IMPORT + "export function main(t: Target) {\n  t.ping();\n}\n", PING, "typed", "ping"),
    "app/other-value.ts": Case(IMPORT + "export function main(t: Target, u: Target) {\n"
                               "  if (u instanceof Grid) {\n    u.stopB();\n  }\n  t.ping();\n}\n", PING, "typed",
                               "ping"),
    "app/similar-name.ts": Case(IMPORT + "export function main(t: Target, t2: Target) {\n  if (t instanceof Grid) {\n"
                                "    t.id;\n  }\n  t2.ping();\n}\n", PING, "typed", "ping"),
    "app/other-function.ts": Case(IMPORT + "function guard(t: Target) {\n  return t instanceof Grid;\n}\n"
                                  "export function main(t: Target) {\n  t.ping();\n}\n", PING, "typed", "ping"),
}
TYPED_STRATEGIES = ("receiver-type", "receiver-type-impl", "inherited", "inherited-impl")


@pytest.fixture(scope="module")
def repo(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    for rel, body in {"package.json": '{"name": "app"}\n', "app/models.ts": MODELS,
                      **{f: c.use for f, c in USES.items()}}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    return root


@pytest.fixture(scope="module")
def indexed(repo):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    with contextlib.redirect_stderr(io.StringIO()):
        info = RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(repo))
        return extract_and_resolve(info, convs=[])


@pytest.fixture(scope="module")
def checked(repo) -> dict[str, set[str]]:
    env = {**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}
    out = subprocess.run(["node", str(CHECKER), str(repo)], capture_output=True, text=True, check=True, env=env).stdout
    found: dict[str, set[str]] = {file: set() for file in USES}
    for r in map(json.loads, out.splitlines()):
        if r["file"] in USES and r["method"] == USES[r["file"]].method:
            found[r["file"]] |= set(r["declared"])
    return found


def _edges(indexed, file: str) -> set[tuple[str, str]]:
    res, rv = indexed
    sym = {s.id: s for s in res.symbols}
    path = {f.id: f.path for f in res.files}
    return {(sym[e.callee_id].qualified_name, e.strategy) for e in rv.calls
            if (path.get(e.caller_id) or path.get(sym[e.caller_id].file_id)) == file
            and (e.method or sym[e.callee_id].name) == USES[file].method}


def _of(answer: str) -> list:
    return [pytest.param(f, id=f) for f, c in USES.items() if c.answer == answer]


@pytest.mark.parametrize("file", list(USES))
def test_the_checker_resolves_the_call_to_the_declaration_the_case_names(checked, file):
    assert checked[file] == {USES[file].declared}


@pytest.mark.parametrize("file", _of("by-name"))
def test_a_value_the_function_tests_with_instanceof_goes_by_name_and_reaches_the_class_it_narrows_to(indexed, file):
    found = _edges(indexed, file)
    assert USES[file].declared in {target for target, _ in found}
    assert not [s for _, s in found if s.removesuffix("-ambiguous") in TYPED_STRATEGIES]


@pytest.mark.parametrize("file", _of("typed"))
def test_a_value_no_function_tests_with_instanceof_keeps_the_type_it_was_declared_with(indexed, file):
    assert _edges(indexed, file) == {(USES[file].declared, "receiver-type")}


@pytest.mark.parametrize("file", _of("by-name"))
def test_the_extraction_records_that_the_flow_may_narrow_the_receiver(indexed, file):
    res, _ = indexed
    use = next(f.id for f in res.files if f.path == file)
    assert {c.receiver_unknown for c in res.calls if c.file_id == use and c.callee_name == USES[file].method} \
        == {NARROWED.reason}
