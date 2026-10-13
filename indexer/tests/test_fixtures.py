"""Golden-file regression for the HTTP integration extractor.

Each folder under tests/fixtures/<name>/ is a tiny repository with an `expected.json` written
by hand (or reviewed line by line) listing the routes it exposes and the outbound calls it
makes. Precision and recall must both be 100 % on fixtures — they are controlled code.

A fixture that reproduces a development pattern also names its convention (`"convention"`: a yaml
path relative to the fixture, or an id / `module:Class` — extensions under indexer/conventions/ are on
sys.path, see conftest.py) and lists what it must produce: `architecture` (the layout detected), `roles` (type name → role), `layers` (every file), `entry_points`
(`Class.Method`), `violations` (the deliberate one), `edges` (CALLS the graph must carry, with the
strategy) and `gaps` (links known to be missing — xfail until they appear, then the test fails
asking to move them to `edges`).

    cd indexer && pip install -e . && pytest -q tests/
Grammars must be cached (TREE_SITTER_LANGUAGE_PACK_CACHE_DIR) — see docs/indexer-evolution.md §4.
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

import pytest

FIXTURES = sorted(p for p in (Path(__file__).parent / "fixtures").iterdir() if (p / "expected.json").exists())


def _extract(root: Path):
    from aidd_indexer.cli import extract_tree
    from aidd_indexer.core.integrations import extract_http
    from aidd_indexer.core.model import RepoInfo

    repo = RepoInfo(tenant="t", name=root.name, ref="main", commit_sha="x", root=str(root))
    res, extractors = extract_tree(repo)
    return extract_http(repo, extractors)


@pytest.mark.parametrize("root", FIXTURES, ids=[p.name for p in FIXTURES])
def test_fixture(root: Path):
    expected = json.loads((root / "expected.json").read_text())
    hr = _extract(root)
    got_eps = sorted({(e.method, e.path, e.handler_name) for e in hr.endpoints})
    exp_eps = sorted({(e["method"], e["path"], e.get("handler")) for e in expected["endpoints"]})
    assert got_eps == exp_eps, f"endpoints differ\n missing={set(exp_eps)-set(got_eps)}\n extra={set(got_eps)-set(exp_eps)}"
    got_calls = sorted({(c.method, c.path, c.line) for c in hr.calls})
    exp_calls = sorted({(c["method"], c["path"], c["line"]) for c in expected["calls"]})
    assert got_calls == exp_calls, f"calls differ\n missing={set(exp_calls)-set(got_calls)}\n extra={set(got_calls)-set(exp_calls)}"
    callers = {(c.method, c.path, c.line): _tail(c.caller_id) for c in hr.calls}
    for c in expected["calls"]:
        if "caller" in c:
            assert callers[(c["method"], c["path"], c["line"])].endswith("." + c["caller"]), (c, callers)
    assert not hr.warnings, hr.warnings


# ---- fixtures of a development pattern: `expected.json` also names the convention that describes it
# and what it must produce — layers, entry points, the deliberate violation, the CALLS chain the graph
# must carry (`edges`) and the links it is known not to see yet (`gaps`).

CONV_FIXTURES = [p for p in FIXTURES if "convention" in json.loads((p / "expected.json").read_text())]


def _tail(symbol_id: str | None) -> str:
    """`t/r@main/sym/Ns.Class.Method#method` → `Ns.Class.Method`."""
    return (symbol_id or "").split("/sym/")[-1].split("#")[0]


@functools.lru_cache(maxsize=None)
def _resolved(root: Path):
    from aidd_indexer import conventions
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo

    expected = json.loads((root / "expected.json").read_text())
    spec = expected["convention"]            # a convention.yaml next to the fixture, or an id / `module:Class`
    spec = {"path": str((root / spec).resolve())} if spec.endswith((".yaml", ".yml")) else {"id": spec}
    convs = conventions.load([spec], root.name)
    repo = RepoInfo(tenant="t", name=root.name, ref="main", commit_sha="x", root=str(root))
    res, rv = extract_and_resolve(repo, convs=convs)
    return expected, res, rv, convs


def _symbols(res, name: str) -> set[str]:
    """Symbols whose qualified name ends with `name` (`Class.Method` or `Class`) on a dot boundary."""
    return {s.id for s in res.symbols if s.qualified_name == name or s.qualified_name.endswith("." + name)}


def _edges(rv, res, frm: str, to: str) -> set[str]:
    a, b = _symbols(res, frm), _symbols(res, to)
    assert a and b, f"fixture lacks {frm if not a else to}"
    return {e.strategy for e in rv.calls if e.caller_id in a and e.callee_id in b}


@pytest.mark.parametrize("root", CONV_FIXTURES, ids=[p.name for p in CONV_FIXTURES])
def test_fixture_convention(root: Path):
    expected, res, rv, convs = _resolved(root)
    if "architecture" in expected:
        assert [getattr(c, "architecture", None) for c in convs] == [expected["architecture"]]
    if "roles" in expected:
        got_roles = {s.name: s.role for s in res.symbols if s.role}
        assert got_roles == expected["roles"], {n: (got_roles.get(n), expected["roles"].get(n))
                                                 for n in got_roles.keys() | expected["roles"].keys() if got_roles.get(n) != expected["roles"].get(n)}
    paths = {f.path for f in res.files}
    assert set(expected["layers"]) <= paths, set(expected["layers"]) - paths
    got_layers = {f.path: f.layer for f in res.files if f.layer}
    exp_layers = {p: l for p, l in expected["layers"].items() if l}
    assert got_layers == exp_layers, {p: (got_layers.get(p), exp_layers.get(p))
                                      for p in got_layers.keys() | exp_layers.keys() if got_layers.get(p) != exp_layers.get(p)}

    got_eps = {".".join(s.qualified_name.split(".")[-2:]) for s in res.symbols if s.is_entry_point}
    assert got_eps == set(expected["entry_points"]), f"missing={set(expected['entry_points']) - got_eps} extra={got_eps - set(expected['entry_points'])}"

    by_id = {f.id: f.path for f in res.files}
    got_v = sorted((v.rule, by_id[v.file_id], v.line) for v in res.violations)
    exp_v = sorted((v["rule"], v["file"], v["line"]) for v in expected["violations"])
    assert got_v == exp_v, f"violations differ\n got={got_v}\n expected={exp_v}\n {[v.message for v in res.violations]}"

    for e in expected["edges"]:
        strategies = _edges(rv, res, e["from"], e["to"])
        assert e["strategy"] in strategies, f"{e['from']} -> {e['to']}: want {e['strategy']}, got {strategies or 'no edge'}"


GAPS = [(p, g) for p in CONV_FIXTURES for g in json.loads((p / "expected.json").read_text()).get("gaps", [])]


@pytest.mark.parametrize("root,gap", GAPS, ids=[f"{p.name}:{g['from']}->{g['to']}" for p, g in GAPS])
def test_fixture_known_gap(root: Path, gap: dict):
    """Links the graph does not carry yet. When one starts to appear, move it to `edges`."""
    _, res, rv, _ = _resolved(root)
    if _edges(rv, res, gap["from"], gap["to"]):
        pytest.fail(f"gap closed ({gap['why']}): move {gap['from']} -> {gap['to']} to `edges` in expected.json")
    pytest.xfail(gap["why"])


def test_wrapped_handlers_resolve_to_symbols():
    """`mux.Handle(p, wrap(h, WithX()))`, `http.HandlerFunc(h)` and `chain(a, b)(h)` all point at `h`'s symbol."""
    hr = _extract(Path(__file__).parent / "fixtures" / "go-wrapped-http")
    assert all(e.handler_id for e in hr.endpoints), [(e.path, e.handler_name) for e in hr.endpoints if not e.handler_id]
