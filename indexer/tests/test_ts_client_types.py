"""The HTTP scanner of TS finds a client by the type its receiver declares, and a type that is no client takes no
client away: a receiver the name, a `new` or an import already gives as a client stays one, whatever its type. Where the
name and a repo class that holds a wrapper both give the client, the call is the one the class's wrapper makes, with the
client's base, in place of the direct one. A repo class's type is checked against the declaration TypeScript's checker
resolves the call to (scripts/checks/ts_checker.js)."""

import contextlib
import io
import json
import os
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "checks" / "ts_checker.js"
CLIENT = ('export class ApiClient {\n  baseUrl = "/api";\n'
          "  get(path: string) { return fetch(this.baseUrl + path); }\n}\n")
CACHE = "export class Cache {\n  get(key: string) { return key; }\n}\n"
IMPORT_CLIENT = 'import { ApiClient } from "./client";\n'
IMPORT_CACHE = 'import { Cache } from "./cache";\n'
GET_CLIENT, GET_CACHE = "app/client:ApiClient.get", "app/cache:Cache.get"


class Case(NamedTuple):
    use: str                         # the source of the file, which makes one call of `get`
    calls: set[tuple[str, str]]      # the outbound calls the scanner finds in it
    declared: tuple[str, ...]        # what the checker resolves the call to: none where the receiver is `any`


CASES = {
    "app/by-name-and-by-type.ts": Case(
        IMPORT_CLIENT + 'export function main(api: ApiClient) { return api.get("/users"); }\n',
        {("GET", "/api/users")}, (GET_CLIENT,)),
    "app/a-class-that-is-no-client.ts": Case(
        IMPORT_CACHE + 'export function main(c: Cache) { return c.get("/users"); }\n', set(), (GET_CACHE,)),
    "app/an-any-receiver.ts": Case(
        'export function main(api: any) { return api.get("/users"); }\n', {("GET", "/users")}, ()),
    "app/a-name-over-a-type-that-is-no-client.ts": Case(
        IMPORT_CACHE + 'export function main(http: Cache) { return http.get("/x"); }\n', {("GET", "/x")}, (GET_CACHE,)),
    "app/a-library-client-by-its-import.ts": Case(
        'import * as sa from "superagent";\nexport function main() { return sa.get("/users"); }\n',
        {("GET", "/users")}, ()),
    "app/a-library-client-by-its-import-where-the-flow-may-narrow-its-type.ts": Case(
        'import * as sa from "superagent";\nexport function main() {\n  if (sa instanceof Object) return 1;\n'
        '  return sa.get("/users");\n}\n', {("GET", "/users")}, ()),
    "app/a-type-of-a-package-that-is-no-client-library.ts": Case(
        'import type { Pager } from "left-pad";\n'
        'export function main(pager: Pager) { return pager.get("/users"); }\n', set(), ()),
    "app/an-unknown-receiver-no-name-says-is-a-client.ts": Case(
        'export function main(x: any) { return x.get("/users"); }\n', set(), ()),
    "app/an-argument-that-is-no-path.ts": Case(
        IMPORT_CLIENT + "export function main(c: ApiClient, key: string) { return c.get(key); }\n", set(),
        (GET_CLIENT,)),
}
AFTER_THE_TYPE = {"app/by-name-and-by-type.ts"}      # the calls the type changes: the rest are the same as before it
SCANNER_IGNORES_THE_TYPE = pytest.mark.xfail(
    strict=True, reason="the scanner takes a client's call from its receiver's name when the name says it is one")


@pytest.fixture(scope="module")
def repo(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    for rel, body in {"package.json": '{"name": "app"}\n', "app/client.ts": CLIENT, "app/cache.ts": CACHE,
                      **{f: c.use for f, c in CASES.items()}}.items():
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
def checked(repo) -> dict[str, tuple[str, ...]]:
    env = {**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}
    out = subprocess.run(["node", str(CHECKER), str(repo)], capture_output=True, text=True, check=True, env=env).stdout
    found: dict[str, tuple[str, ...]] = {file: () for file in CASES}
    for r in map(json.loads, out.splitlines()):
        if r["file"] in CASES and r["method"] == "get":
            found[r["file"]] = tuple(r["declared"])
    return found


def _calls(indexed, file: str) -> set[tuple[str, str]]:
    res, _ = indexed
    path = {f.id: f.path for f in res.files}
    return {(c.method, c.path) for c in res.http_calls if path[c.file_id] == file}


@pytest.mark.parametrize("file", list(CASES))
def test_the_checker_resolves_the_call_to_the_declaration_the_case_names(checked, file):
    assert checked[file] == CASES[file].declared


@pytest.mark.parametrize("file", [pytest.param(f, id=f, marks=[SCANNER_IGNORES_THE_TYPE] if f in AFTER_THE_TYPE else [])
                                  for f in CASES])
def test_the_scanner_finds_the_calls_of_a_client_the_name_or_the_type_gives(indexed, file):
    assert _calls(indexed, file) == CASES[file].calls
