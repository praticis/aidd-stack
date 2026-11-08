"""TS's HTTP paths the extractor still misreads, and the clients it does not take by the type a receiver declares where
the type is an interface. Each case states the right answer and is a strict xfail with the reason: when the extractor
learns it, the case passes, the xfail fails the suite, and the mark has to go."""

import contextlib
import io

import pytest

INSTANCE_FIELD = {
    "package.json": '{"name": "app"}\n',
    "lib/config.ts": "class Boot {\n  namespace = 'default';\n  constructor(options: object) { Object.assign(this, "
                     "options); }\n}\nexport const config = new Boot({});\n",
    "lib/srv.ts": "export function getBackendSrv() { return { post(url: string, body: object) {} }; }\n",
    "app/api.ts": "import { config } from '../lib/config';\nimport { getBackendSrv } from '../lib/srv';\n"
                  "export function create(x: { v: string }) {\n  return getBackendSrv().post(`/apis/${x.v}/namespaces/"
                  "${config.namespace}/datasources`, x);\n}\n",
}
AN_INTERFACE_THAT_A_CLIENT_IMPLEMENTS = {
    "package.json": '{"name": "app"}\n',
    "app/port.ts": "export interface Port { get(path: string): Promise<unknown> }\nexport class Impl implements Port {\n"
                   '  baseUrl = "/api";\n  get(path: string) { return fetch(this.baseUrl + path); }\n}\n',
    "app/use.ts": 'import { Port } from "./port";\nexport function main(port: Port) { return port.get("/users"); }\n',
}


def case(id, files, want, why):
    return pytest.param(files, want, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


def _extract(tmp_path, files):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, body in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(tmp_path)),
                                   convs=[])[0]


CASES = [
    case("a-field-an-instance-fills-at-run-time-is-no-constant-of-a-path", INSTANCE_FIELD,
         "/apis/{param}/namespaces/{param}/datasources",
         "a field of an instance is read as the constant its class declares, which a constructor may overwrite"),
]
CLIENTS = [
    case("an-interface-typed-receiver-reaches-the-wrapper-of-the-class-that-implements-it",
         AN_INTERFACE_THAT_A_CLIENT_IMPLEMENTS, {("GET", "/api/users")},
         "the scanner takes the method of the receiver's declared type, an interface, which no wrapper is published "
         "under: the wrapper is the class's that implements it"),
]


@pytest.mark.parametrize("files, path", CASES)
def test_a_path_holds_a_constant_only_where_the_declaration_fixes_it(tmp_path, files, path):
    assert [e.path for e in _extract(tmp_path, files).endpoints] == [path]


@pytest.mark.parametrize("files, calls", CLIENTS)
def test_a_receiver_is_a_client_only_where_its_declared_type_is_one(tmp_path, files, calls):
    assert {(c.method, c.path) for c in _extract(tmp_path, files).http_calls} == calls
