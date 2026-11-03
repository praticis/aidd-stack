"""TS's HTTP paths the extractor still misreads. Each case states the right answer and is a strict xfail with the
reason: when the extractor learns it, the case passes, the xfail fails the suite, and the mark has to go."""

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


def case(id, files, path, why):
    return pytest.param(files, path, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


CASES = [
    case("a-field-an-instance-fills-at-run-time-is-no-constant-of-a-path", INSTANCE_FIELD,
         "/apis/{param}/namespaces/{param}/datasources",
         "a field of an instance is read as the constant its class declares, which a constructor may overwrite"),
]


@pytest.mark.parametrize("files, path", CASES)
def test_a_path_holds_a_constant_only_where_the_declaration_fixes_it(tmp_path, files, path):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, body in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        res, _ = extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(tmp_path)),
                                     convs=[])
    assert [e.path for e in res.endpoints] == [path]
