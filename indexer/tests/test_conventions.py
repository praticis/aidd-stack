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


SDK_GO = '''package api

import "context"

type Server struct{}
type Gateway struct{}

func (s *Server) Route(method, path string, h func()) {}
func (g *Gateway) DoJSON(ctx context.Context, method, path string, out any) error { return nil }
func (g *Gateway) Do(ctx context.Context, path string) error { return nil }

func ping() {}

func Register(srv *Server, gw *Gateway, ctx context.Context) {
	srv.Route("GET", "/v1/ping", ping)
	_ = gw.DoJSON(ctx, "POST", "/v1/orders", nil)
	_ = gw.Do(ctx, "/v1/health")
}
'''


def _sdk_repo(tmp_path: Path) -> Path:
    root = tmp_path / "svc"
    (root / "internal").mkdir(parents=True)
    (root / "go.mod").write_text("module example.com/svc\n\ngo 1.22\n")
    (root / "internal" / "api.go").write_text(SDK_GO)
    return root


def _http(root: Path, convs):
    from aidd_indexer import conventions
    from aidd_indexer.cli import extract_tree
    from aidd_indexer.core.integrations import extract_http
    from aidd_indexer.core.model import RepoInfo
    repo = RepoInfo(tenant="t", name=root.name, ref="main", commit_sha="x", root=str(root))
    res, ex = extract_tree(repo, conventions.scan_patterns(convs))
    return extract_http(repo, ex, conventions.scan_patterns(convs))


def test_convention_route_and_client_patterns(tmp_path: Path):
    """An internal SDK's registrar / client methods are invisible to the generic scanner and
    visible once a convention declares them (F0.4.5)."""
    from aidd_indexer import conventions
    root = _sdk_repo(tmp_path)
    plain = _http(root, [])
    assert plain.endpoints == [] and plain.calls == []

    spec = {"id": "sdk",
            "route_patterns": {"registrars": {"Route": None}},
            "client_patterns": {"methods": {"DoJSON": None}, "receivers": ["gw"]}}
    f = tmp_path / "convention.yaml"
    f.write_text(yaml.safe_dump(spec))
    hr = _http(root, conventions.load([{"path": str(f)}], root.name))
    assert [(e.method, e.path, e.handler_name, e.framework) for e in hr.endpoints] == [("GET", "/v1/ping", "ping", "convention")]
    assert sorted((c.method, c.path, c.via) for c in hr.calls) == [("ANY", "/v1/health", "gw.Do"), ("POST", "/v1/orders", "gw.DoJSON")]
