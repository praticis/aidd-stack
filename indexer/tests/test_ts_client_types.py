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
USERS = ('import { ApiClient } from "./client";\nexport class Users {\n  constructor(private c: ApiClient) {}\n'
         "  fetch(path: string) { return this.c.get(path); }\n}\n")
OTHER = "export class ApiClient {\n  get(key: string) { return key; }\n}\n"
IMPORT_CLIENT = 'import { ApiClient } from "./client";\n'
IMPORT_CACHE = 'import { Cache } from "./cache";\n'
GET_CLIENT, GET_CACHE = "app/client:ApiClient.get", "app/cache:Cache.get"


class Case(NamedTuple):
    use: str                         # the source of the file, which makes one call of `get`
    calls: set[tuple[str, str]]      # the outbound calls the scanner finds in it
    declared: tuple[str, ...]        # what the checker resolves the call to: none where the receiver is `any`
    method: str = "get"              # the method the file calls


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
    "app/a-class-of-a-name-a-wrapper-class-has.ts": Case(
        'import { ApiClient } from "./other";\nexport function main(c: ApiClient) { return c.get("/users"); }\n', set(),
        ("app/other:ApiClient.get",)),
    "app/an-override-that-is-no-wrapper.ts": Case(
        IMPORT_CLIENT + "class Mock extends ApiClient {\n  get(path: string) { return Promise.resolve(path); }\n}\n"
        'export function main(m: Mock) { return m.get("/users"); }\n', set(), ("app/an-override-that-is-no-wrapper:Mock.get",)),
    "app/a-method-a-base-declares.ts": Case(
        IMPORT_CLIENT + "class Sub extends ApiClient {}\n"
        'export function main(s: Sub) { return s.get("/users"); }\n', {("GET", "/api/users")}, (GET_CLIENT,)),
    "app/a-type-of-a-client-library-that-is-no-client.ts": Case(
        'import type { MockAgent } from "undici";\nexport function main(agent: MockAgent) { return agent.get("/api/x"); }\n',
        set(), ()),
    "app/a-type-of-a-client-library-that-is-headers.ts": Case(
        'import type { AxiosHeaders } from "axios";\nexport function main(h: AxiosHeaders) { return h.get("/x"); }\n',
        set(), ()),
    "app/a-library-type-under-another-name.ts": Case(
        'import type { AxiosInstance as Http } from "axios";\n'
        'export function main(backend: Http) { return backend.get("/users"); }\n', {("GET", "/users")}, ()),
    "app/a-chain-of-wrappers-through-a-typed-receiver.ts": Case(
        'import { Users } from "./users";\nexport function main(s: Users) { return s.fetch("/users"); }\n',
        {("GET", "/api/users")}, ("app/users:Users.fetch",), "fetch"),
    "app/a-library-type-under-a-namespace-import.ts": Case(
        'import type * as ax from "axios";\nexport function main(backend: ax.AxiosInstance) { return backend.get("/users"); }\n',
        {("GET", "/users")}, ()),
    "app/a-library-type-in-an-await-with-type-arguments.ts": Case(
        'import type { AxiosInstance } from "axios";\n'
        'export async function main(backend: AxiosInstance) { return await backend.get<string>("/users"); }\n',
        {("GET", "/users")}, ()),
    "app/an-optional-receiver.ts": Case(
        IMPORT_CLIENT + 'export function main(c?: ApiClient) { return c?.get("/users"); }\n',
        {("GET", "/api/users")}, (GET_CLIENT,)),
    "app/a-non-null-receiver.ts": Case(
        IMPORT_CLIENT + 'export function main(c?: ApiClient) { return c!.get("/users"); }\n',
        {("GET", "/api/users")}, (GET_CLIENT,)),
    "app/a-receiver-cast-to-the-class.ts": Case(
        IMPORT_CLIENT + 'export function main(c: unknown) { return (c as ApiClient).get("/users"); }\n',
        {("GET", "/api/users")}, (GET_CLIENT,)),
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


@pytest.fixture(scope="module")
def repo(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    for rel, body in {"package.json": '{"name": "app"}\n', "app/client.ts": CLIENT, "app/cache.ts": CACHE, "app/other.ts": OTHER, "app/users.ts": USERS,
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
        if r["file"] in CASES and r["method"] == CASES[r["file"]].method:
            found[r["file"]] = tuple(r["declared"])
    return found


def _calls(indexed, file: str) -> set[tuple[str, str]]:
    res, _ = indexed
    path = {f.id: f.path for f in res.files}
    return {(c.method, c.path) for c in res.http_calls if path[c.file_id] == file}


@pytest.mark.parametrize("file", list(CASES))
def test_the_checker_resolves_the_call_to_the_declaration_the_case_names(checked, file):
    assert checked[file] == CASES[file].declared


@pytest.mark.parametrize("file", list(CASES))
def test_the_scanner_finds_the_calls_of_a_client_the_name_or_the_type_gives(indexed, file):
    assert _calls(indexed, file) == CASES[file].calls
