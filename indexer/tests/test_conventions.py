"""The conventions seam: a declarative convention layers files, refines target hints and emits
Violation candidates — and with no convention configured the result is untouched."""
from __future__ import annotations

from pathlib import Path

import yaml

FIX = Path(__file__).parent / "fixtures" / "go-http-mix"


def _run(convs):
    from aidd_indexer import conventions
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo

    repo = RepoInfo(tenant="t", name=FIX.name, ref="main", commit_sha="x", root=str(FIX))
    return extract_and_resolve(repo, convs=convs)


def test_without_conventions_is_untouched():
    res, _ = _run([])
    assert all(f.layer is None for f in res.files) and all(m.layer is None for m in res.modules)
    assert res.violations == []


def test_declarative_convention(tmp_path: Path):
    from aidd_indexer import conventions
    spec = {
        "id": "hex",
        "layers": {"adapters-in": ["internal/adapters/inbound/**"], "adapters-out": ["internal/adapters/outbound/**"]},
        "targets": {"internal/adapters/outbound/billing/**": "billing-svc"},
        "rules": [
            {"id": "routes-in", "endpoints_only_in": ["adapters-in"], "severity": "warning"},
            {"id": "clients-wrong-layer", "http_calls_only_in": ["adapters-in"], "severity": "error"},   # deliberately wrong → fires
        ],
    }
    p = tmp_path / "convention.yaml"
    p.write_text(yaml.safe_dump(spec))
    convs = conventions.load([{"path": str(p), "repos": ["go-*"]}], FIX.name)
    assert [c.id for c in convs] == ["hex"]
    assert conventions.load([{"path": str(p), "repos": ["other-*"]}], FIX.name) == []   # repo filter

    res, _ = _run(convs)
    layers = {f.path: f.layer for f in res.files if f.layer}
    assert layers["internal/adapters/outbound/billing/client.go"] == "adapters-out"
    assert layers["internal/adapters/inbound/http/server.go"] == "adapters-in"
    assert {m.path: m.layer for m in res.modules}["internal/adapters/outbound/billing"] == "adapters-out"
    assert {c.target_hint for c in res.http_calls} == {"billing-svc"}
    rules = {v.rule for v in res.violations}
    assert rules == {"clients-wrong-layer"}, res.violations           # every route is in adapters-in → no `routes-in`
    assert len(res.violations) == len(res.http_calls)
    v = res.violations[0]
    assert v.convention == "hex" and v.severity == "error" and v.id.startswith("t/go-http-mix@main/violation/hex.clients-wrong-layer/")
