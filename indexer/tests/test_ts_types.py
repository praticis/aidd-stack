"""TS's and JS's answers to what type the code declares for a call's receiver, which the resolver asks to type it for
`CALLS` and the HTTP scanner to find a client's calls. The declarations a case names are the ones TypeScript's own
checker resolves its call to: every case is checked against the checker of the compiler the test image pins
(scripts/checks/ts_checker.js), which reads and types the files and runs nothing. A case the declarations in sight
decide is typed; one where the checker narrows a union by control flow, infers through a generic or reads a result the
function does not declare stays unknown, since a declaration's answer does not give it. The scope cases are where a
name bound to the wrong declaration would give a wrong type; every name of them binds as the compiler's binder binds it
(test_ts_scopes.py)."""

import contextlib
import io
import json
import os
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "checks" / "ts_checker.js"
MODELS = """export interface IRepo { run(): void; }
export class Base { run() {} }
export class A { run() {} send() {} }
export class B extends Base implements IRepo { run() {} }
export function make(): B { return new B(); }
export function build() { return new B(); }
export const shared = new B();
"""
NAMED = ("same-file", "same-module", "unique-name")
B_RUN, BASE_RUN = "app/models:B.run", "app/models:Base.run"


class Case(NamedTuple):
    use: str                        # app/use.<ext>; it makes one call of its method
    declared: tuple[str, ...]       # what the checker resolves the call to
    answer: str                     # typed: the declarations decide it; unknown: they do not; external: no repo method
    ext: str = "ts"
    method: str = "run"
    reason: str | None = None       # unknown and external: why the declarations in sight give no type


IMPORT_B = 'import { B } from "./models";\n'

DECLARED = {
    "this": Case("class C {\n  run() {}\n  go() { return this.run(); }\n}\n", ("app/use:C.run",), "typed"),
    "this-in-a-fields-initializer": Case("class C {\n  run() {}\n  go = () => this.run();\n}\n", ("app/use:C.run",),
                                         "typed"),
    "this-in-an-arrow-function-in-a-method": Case(
        "class C {\n  run() {}\n  go() {\n    const f = () => this.run();\n    return f();\n  }\n}\n",
        ("app/use:C.run",), "typed"),
    "a-method-of-a-repo-base": Case(
        'import { Base } from "./models";\nclass C extends Base {\n  go() { return this.run(); }\n}\n', (BASE_RUN,),
        "typed"),
    "a-new-expression": Case(IMPORT_B + "export function main() { return new B().run(); }\n", (B_RUN,), "typed"),
    "a-local-of-a-new-expression": Case(
        IMPORT_B + "export function main() {\n  const x = new B();\n  return x.run();\n}\n", (B_RUN,), "typed"),
    "a-typed-parameter": Case(IMPORT_B + "export function main(x: B) { return x.run(); }\n", (B_RUN,), "typed"),
    "a-typed-local": Case('import { B, Base } from "./models";\n'
                          "export function main() {\n  const x: Base = new B();\n  return x.run();\n}\n", (BASE_RUN,),
                          "typed"),
    "a-parameter-property": Case(
        IMPORT_B + "class C {\n  constructor(private readonly b: B) {}\n  go() { return this.b.run(); }\n}\n", (B_RUN,),
        "typed"),
    "a-typed-field": Case(IMPORT_B + "class C {\n  b!: B;\n  go() { return this.b.run(); }\n}\n", (B_RUN,), "typed"),
    "a-field-of-a-new-expression": Case(IMPORT_B + "class C {\n  b = new B();\n  go() { return this.b.run(); }\n}\n",
                                        (B_RUN,), "typed"),
    "a-declared-result": Case('import { make } from "./models";\nexport function main() { return make().run(); }\n',
                              (B_RUN,), "typed"),
    "a-local-of-a-declared-result": Case(
        'import { make } from "./models";\nexport function main() {\n  const x = make();\n  return x.run();\n}\n',
        (B_RUN,), "typed"),
    "an-as-expression": Case(IMPORT_B + "export function main(x: unknown) { return (x as B).run(); }\n", (B_RUN,),
                             "typed"),
    "an-optional-chain": Case(IMPORT_B + "export function main(x?: B) { return x?.run(); }\n", (B_RUN,), "typed"),
    "an-exported-instance": Case(
        'import { shared } from "./models";\nexport function main() { return shared.run(); }\n', (B_RUN,), "typed"),
    "an-aliased-import": Case(
        'import { B as Bee } from "./models";\nexport function main() { return new Bee().run(); }\n', (B_RUN,),
        "typed"),
    "a-namespace-import": Case('import * as m from "./models";\nexport function main() { return new m.B().run(); }\n',
                               (B_RUN,), "typed"),
    "a-call-on-an-interface": Case(
        'import { IRepo } from "./models";\nexport function main(r: IRepo) { return r.run(); }\n',
        ("app/models:IRepo.run",), "typed"),
    "a-constrained-type-parameter": Case(
        'import { Base } from "./models";\nexport function main<T extends Base>(x: T) { return x.run(); }\n',
        (BASE_RUN,), "typed"),
    "a-typed-parameter-in-tsx": Case(IMPORT_B + "export function main(x: B) { return x.run(); }\n", (B_RUN,), "typed",
                                     ext="tsx"),
    "a-new-expression-in-js": Case(IMPORT_B + "export function main() { return new B().run(); }\n", (B_RUN,), "typed",
                                   ext="js"),
    "this-in-js": Case("class C {\n  run() {}\n  go() { return this.run(); }\n}\n", ("app/use:C.run",), "typed",
                       ext="js"),
}

UNDECIDED = {
    "any": Case("export function main(x: any) { return x.run(); }\n", (), "unknown", reason="a value of type any"),
    "a-js-parameter": Case("export function main(x) { return x.run(); }\n", (), "unknown", ext="js",
                           reason="a JS parameter, which declares no type"),
    "this-in-a-function-in-a-method": Case(
        "class C {\n  run() {}\n  go() {\n    const f = function () { return this.run(); };\n    return f;\n  }\n}\n",
        (), "unknown", reason="a function's own this, which the class around it does not bind"),
    "an-unconstrained-type-parameter": Case("export function main<T>(x: T) { return x.run(); }\n", (), "unknown",
                                            reason="a type parameter with no constraint"),
    "a-union": Case('import { A, B } from "./models";\nexport function main(x: A | B) { return x.run(); }\n',
                    ("app/models:A.run", B_RUN), "unknown", reason="a union of several types"),
    "an-intersection": Case(
        'import { A, Base } from "./models";\nexport function main(x: A & Base) { return x.run(); }\n',
        ("app/models:A.run", BASE_RUN), "unknown", reason="an intersection of several types"),
    "a-union-narrowed-by-control-flow": Case(
        'import { A, B } from "./models";\nexport function main() {\n  let x: A | B = new B();\n  return x.run();\n}\n',
        (B_RUN,), "unknown", reason="a union the checker narrows by control flow"),
    "a-result-the-function-does-not-declare": Case(
        'import { build } from "./models";\nexport function main() { return build().run(); }\n', (B_RUN,), "unknown",
        reason="a result the function does not declare"),
    "a-callback-parameter": Case(IMPORT_B + "export function main() { [new B()].forEach((v) => v.run()); }\n",
                                 (B_RUN,), "unknown", reason="a type the checker infers through a generic"),
    "a-value-of-a-package-class": Case(
        'import { Client } from "some-package";\nexport function main() {\n  const c = new Client();\n'
        "  return c.send();\n}\n", (), "external", method="send", reason="a type a package declares"),
}

# -- which declaration a name binds to, as the language scopes it -------------------------------------------------
SCOPES = {
    "a-block-that-shadows": Case(
        'import { A, B } from "./models";\nexport function main(flag: boolean) {\n  const x = new A();\n'
        "  if (flag) {\n    const x = new B();\n    void x;\n  }\n  return x.run();\n}\n", ("app/models:A.run",),
        "typed"),
    "a-var-used-before-its-declaration": Case(
        IMPORT_B + "export function main() {\n  x.run();\n  var x = new B();\n}\n", (B_RUN,), "typed"),
    "a-let-reassigned-from-any": Case(
        IMPORT_B + "export function main(s: string) {\n  let x = new B();\n  x = JSON.parse(s);\n"
        "  return x.run();\n}\n", (B_RUN,), "typed"),
    "a-function-declared-after-its-use": Case(
        IMPORT_B + "export function main() {\n  return made().run();\n  function made(): B { return new B(); }\n}\n",
        (B_RUN,), "typed"),
    "a-closure": Case(IMPORT_B + "export function main() {\n  const x = new B();\n  const f = () => x.run();\n"
                      "  return f();\n}\n", (B_RUN,), "typed"),
    "a-destructured-parameter": Case(IMPORT_B + "export function main({ x }: { x: B }) { return x.run(); }\n",
                                     (B_RUN,), "typed"),
    "a-type-parameter-that-shadows-an-import": Case(
        IMPORT_B + "export function main<B>(x: B) { return x.run(); }\n", (), "unknown",
        reason="a type parameter with no constraint"),
    "a-for-of-variable": Case(IMPORT_B + "export function main(xs: B[]) {\n  for (const x of xs) x.run();\n}\n",
                              (B_RUN,), "unknown", reason="a type the checker infers through a generic"),
}

CASES = DECLARED | UNDECIDED | SCOPES

# -- the scanner: a client's calls, found through the type its receiver declares -----------------------------------
CLIENT = ('export class ApiClient {\n  baseUrl = "/api";\n'
          "  get(path: string) { return fetch(this.baseUrl + path); }\n}\n"
          "export function client(): ApiClient { return new ApiClient(); }\n")
IMPORT_CLIENT = 'import { ApiClient } from "./client";\n'
USERS = {("GET", "/api/users")}


class Scan(NamedTuple):
    use: str
    calls: set[tuple[str, str]]             # the outbound calls the scanner finds
    declared: tuple[str, ...] | None = None  # what the checker resolves the client's call to; None for a package's
                                             # type, which the test image does not hold


GET_USERS = ("app/client:ApiClient.get",)
FOUND = {
    "a-module-client": Scan('import axios from "axios";\nconst api = axios.create({ baseURL: "/api" });\n'
                            'export function main() { return api.get("/users"); }\n', USERS),
    "a-client-named-for-its-role": Scan(
        'import { HttpClient } from "@angular/common/http";\nexport class Users {\n'
        '  constructor(private http: HttpClient) {}\n  list() { return this.http.get("/api/users"); }\n}\n', USERS),
    "a-repo-client-in-a-module-constant": Scan(
        IMPORT_CLIENT + 'const c = new ApiClient();\nexport function main() { return c.get("/users"); }\n', USERS,
        GET_USERS),
    "a-repo-client-in-a-local": Scan(
        IMPORT_CLIENT + "export function main() {\n  const backend = new ApiClient();\n"
        '  return backend.get("/users");\n}\n', USERS, GET_USERS),
}
TYPED_CLIENTS = {
    "a-parameter-of-a-repo-clients-type": Scan(
        IMPORT_CLIENT + 'export function main(c: ApiClient) { return c.get("/users"); }\n', USERS, GET_USERS),
    "a-parameter-property-of-a-repo-clients-type": Scan(
        IMPORT_CLIENT + 'export class Users {\n  constructor(private readonly c: ApiClient) {}\n'
        '  list() { return this.c.get("/users"); }\n}\n', USERS, GET_USERS),
    "a-field-of-a-new-repo-client": Scan(
        IMPORT_CLIENT + 'export class Users {\n  c = new ApiClient();\n  list() { return this.c.get("/users"); }\n}\n',
        USERS, GET_USERS),
    "a-declared-result-of-a-repo-client": Scan(
        'import { client } from "./client";\nexport function main() { return client().get("/users"); }\n', USERS,
        GET_USERS),
    "a-parameter-of-a-client-librarys-type": Scan(
        'import type { AxiosInstance } from "axios";\n'
        'export function main(backend: AxiosInstance) { return backend.get("/users"); }\n', {("GET", "/users")}),
    "a-parameter-property-of-a-client-librarys-type": Scan(
        'import { AxiosInstance } from "axios";\nexport class Users {\n'
        "  constructor(private readonly backend: AxiosInstance) {}\n"
        '  list() { return this.backend.get("/users"); }\n}\n', {("GET", "/users")}),
}
SCANS = FOUND | TYPED_CLIENTS


def _files(name: str) -> dict[str, str]:
    if name in CASES:
        return {"app/models.ts": MODELS, f"app/use.{CASES[name].ext}": CASES[name].use}
    return {"app/client.ts": CLIENT, "app/use.ts": SCANS[name].use}


def _write(root: Path, name: str) -> None:
    for rel, body in {"package.json": '{"name": "app"}\n', **_files(name)}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)


@pytest.fixture(scope="module")
def checked(tmp_path_factory) -> dict[str, tuple[str, ...]]:
    """What the checker resolves each case's call of its method to, every case in one run of the compiler."""
    roots = {}
    for name in [*CASES, *(n for n, scan in SCANS.items() if scan.declared is not None)]:
        roots[name] = tmp_path_factory.mktemp(name)
        _write(roots[name], name)
    out = subprocess.run(["node", str(CHECKER), *map(str, roots.values())], capture_output=True, text=True, check=True,
                         env={**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}).stdout
    by_root = {str(root): name for name, root in roots.items()}
    found = {}
    for row in map(json.loads, out.splitlines()):
        name = by_root[row["project"]]
        if row["file"].startswith("app/use.") and row["method"] == (CASES[name].method if name in CASES else "get"):
            found[name] = tuple(row["declared"])
    return found


def _extract(root: Path, name: str):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    _write(root, name)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)),
                                   convs=[])


def _edges(root: Path, name: str) -> set[tuple[str, str]]:
    """The targets and strategies of the edges of the case's calls of its method."""
    res, rv = _extract(root, name)
    case = CASES[name]
    sym = {s.id: s for s in res.symbols}
    use = next(f.id for f in res.files if f.path.startswith("app/use."))
    return {(sym[e.callee_id].qualified_name, e.strategy) for e in rv.calls
            if use in (e.caller_id, getattr(sym.get(e.caller_id), "file_id", None))
            and (e.method or sym[e.callee_id].name) == case.method}


def _typed(edges: set[tuple[str, str]]) -> set[str]:
    return {target for target, strategy in edges if strategy.removesuffix("-ambiguous") not in NAMED}


def _cases(answer: str, why: str | None = None) -> list:
    marks = [pytest.mark.xfail(strict=True, reason=why)] if why else []
    return [pytest.param(name, id=name, marks=marks) for name, c in CASES.items() if c.answer == answer]


@pytest.mark.parametrize("name", [*CASES, *(n for n, scan in SCANS.items() if scan.declared is not None)])
def test_the_checker_resolves_the_call_to_the_declarations_the_case_names(checked, name):
    assert checked[name] == (CASES[name].declared if name in CASES else SCANS[name].declared)


@pytest.mark.parametrize("name", _cases("typed", "TS's receivers have no type yet"))
def test_a_declared_receiver_reaches_the_declaration_the_checker_names(tmp_path, name):
    assert _edges(tmp_path, name) == {(CASES[name].declared[0], "receiver-type")}


@pytest.mark.parametrize("name", _cases("unknown"))
def test_no_type_where_the_declarations_in_sight_do_not_decide(tmp_path, name):
    assert _typed(_edges(tmp_path, name)) == set()


@pytest.mark.parametrize("name", _cases("external", "a value of a package's type reaches the repo's homonym by name"))
def test_a_method_of_a_package_type_reaches_no_homonym_of_the_repo(tmp_path, name):
    assert _edges(tmp_path, name) == set()


@pytest.mark.parametrize("name", [pytest.param(n, id=n) for n in FOUND] + [
    pytest.param(n, id=n, marks=pytest.mark.xfail(
        strict=True, reason="the scanner knows a client by its receiver's name or by a value it constructs only"))
    for n in TYPED_CLIENTS])
def test_a_clients_calls_are_found_through_the_type_its_receiver_declares(tmp_path, name):
    res, _ = _extract(tmp_path, name)
    assert {(c.method, c.path) for c in res.http_calls} == SCANS[name].calls
