"""Call resolution (F0.7.1): static receiver types in Go and the production→test exclusion."""
from __future__ import annotations

import io
import contextlib
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "go-receiver-types"


def _resolve():
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    repo = RepoInfo(tenant="t", name=FIX.name, ref="main", commit_sha="x", root=str(FIX))
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(repo)
    sym = {s.id: s for s in res.symbols}
    edges = {(e.line, sym[e.caller_id].name if e.caller_id in sym else "<file>"): (sym[e.callee_id].qualified_name, e.strategy)
             for e in rv.calls if sym[e.callee_id].name == "Validate"}
    return res, rv, edges


def test_receiver_types_pick_the_right_validate():
    _, _, edges = _resolve()
    assert edges[(19, "Execute")] == ("internal.domain.password.Policy.Validate", "receiver-type")      # struct field uc.policy
    assert edges[(26, "Check")] == ("internal.domain.password.Policy.Validate", "receiver-type")        # typed parameter
    assert edges[(31, "CheckEmail")] == ("internal.domain.email.Address.Validate", "receiver-type")     # composite literal
    assert edges[(37, "CheckDefault")] == ("internal.domain.password.Policy.Validate", "receiver-type") # constructor return type


def test_promoted_fields_through_embedded_struct():
    """handler (s Server{Config}) calling s.Complete.Execute(): Complete is a promoted field of Config."""
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    repo = RepoInfo(tenant="t", name=FIX.name, ref="main", commit_sha="x", root=str(FIX))
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(repo)
    sym = {s.id: s for s in res.symbols}
    got = {(sym[e.caller_id].name, sym[e.callee_id].qualified_name, e.strategy) for e in rv.calls if sym[e.caller_id].name == "passwordResetComplete"}
    assert ("passwordResetComplete", "internal.app.usecases.Complete.Execute", "receiver-type") in got
    assert ("passwordResetComplete", "internal.domain.password.Policy.Validate", "receiver-type") in got


def test_multi_value_helper_types_the_local():
    """`uc, _ := setup(t)` with `func setup(t) (*Complete, Repo)` → uc is *Complete."""
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    repo = RepoInfo(tenant="t", name=FIX.name, ref="main", commit_sha="x", root=str(FIX))
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(repo)
    sym = {s.id: s for s in res.symbols}
    assert any(sym[e.caller_id].name == "TestExecute" and sym[e.callee_id].qualified_name == "internal.app.usecases.Complete.Execute"
               and e.strategy == "receiver-type" for e in rv.calls)


def test_test_code_can_target_its_own_fakes():
    _, _, edges = _resolve()
    assert edges[(16, "TestExecute")] == ("internal.app.usecases.fakePolicy.Validate", "receiver-type")


def test_production_calls_never_resolve_to_test_symbols():
    res, rv, _ = _resolve()
    sym = {s.id: s for s in res.symbols}
    files = {f.id: f.path for f in res.files}
    for e in rv.calls:
        caller_file = files.get(sym[e.caller_id].file_id) if e.caller_id in sym else ""
        if caller_file and not caller_file.endswith("_test.go"):
            assert not files[sym[e.callee_id].file_id].endswith("_test.go"), (caller_file, sym[e.callee_id].qualified_name)


def test_interface_calls_stay_unresolved():
    res, rv, _ = _resolve()
    sym = {s.id: s for s in res.symbols}
    assert not any(sym[e.callee_id].name == "Save" for e in rv.calls)      # Repo.Save is an interface method: no edge
