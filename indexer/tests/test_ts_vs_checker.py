"""The comparator of TS CALLS edges against the TypeScript checker (scripts/judgment/ts_vs_checker.py), on dry-runs and
checker rows made for the purpose: every verdict, the replaced and the lost, a `.d.ts` pair, a caller that is no TS file."""
import gzip
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("ts_vs_checker", Path(__file__).resolve().parent.parent / "scripts" / "judgment" / "ts_vs_checker.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

P = "t/r@main"


def sym(path, qual, kind="method"):
    return {"id": f"{P}/sym/{path}:{qual}#{kind}", "file_id": f"{P}/file/{path}.ts", "qualified_name": f"{path}:{qual}"}


def file(path, ext=".ts"):
    return {"id": f"{P}/file/{path}{ext}", "path": f"{path}{ext}", "language": "typescript"}


def call(caller, callee, line, strategy):
    return {"caller_id": caller["id"], "callee_id": callee["id"], "line": line, "strategy": strategy}


MAIN = sym("src/use", "main", "function")
PY_MAIN = {"id": f"{P}/sym/tools/run:main#function", "file_id": f"{P}/file/tools/run.py", "qualified_name": "tools/run:main"}
FOO = sym("src/a", "Foo.run")
BAR = sym("src/b", "Bar.run")
THING = sym("src/x", "Thing.m")
BASE = sym("src/base", "Base.walk")
ONLY = sym("src/c", "Only.lone")
JS_MAIN = {"id": f"{P}/sym/src/app:start#function", "file_id": f"{P}/file/src/app.js", "qualified_name": "src/app:start"}
MANY = [sym("src/m", f"M{i}.go") for i in range(8)]
SYMBOLS = [MAIN, PY_MAIN, JS_MAIN, FOO, BAR, THING, BASE, ONLY, *MANY]
FILES = [file("src/use"), file("tools/run", ".py"), file("src/app", ".js"), file("src/a"), file("src/b"), file("src/x"), file("src/base"),
         file("src/c"), file("src/m")]


def run(calls):
    return {"files": FILES, "symbols": SYMBOLS, "calls": calls}


def site(line, method, *declared):
    return {"file": "src/use.ts", "line": line, "method": method, "declared": list(declared)}


@pytest.fixture
def written(tmp_path):
    def write(before, after, rows):
        for name, calls in (("before", before), ("after", after)):
            (tmp_path / name).mkdir()
            with gzip.open(tmp_path / name / "r.json.gz", "wt") as out:
                json.dump(run(calls), out)
        rows_file = tmp_path / "checker.jsonl"
        rows_file.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        return str(tmp_path / "before"), str(tmp_path / "after"), str(rows_file)
    return write


def analyse(written, before, after, rows):
    b, a, c = written(before, after, rows)
    return tool.Analysis(tool.load(b, "r"), tool.load(a, "r"), tool.checker_sites(c))


ADDED = [
    call(MAIN, FOO, 3, "receiver-type"),         # the checker agrees
    call(MAIN, BAR, 4, "receiver-type"),         # the checker names Foo
    call(MAIN, ONLY, 5, "receiver-type"),        # no row for the call
    call(MAIN, BASE, 6, "inherited"),            # the checker names no declaration
    call(MAIN, FOO, 7, "receiver-type"),         # a package's
    call(MAIN, THING, 8, "receiver-type-ambiguous"),   # a .d.ts pair
    call(MAIN, FOO, 9, "name"),                  # by name: not a typed edge
    call(PY_MAIN, FOO, 10, "receiver-type"),     # made in a Python file
]
ROWS = [site(3, "run", "src/a:Foo.run"), site(4, "run", "src/a:Foo.run"), site(6, "walk"), site(7, "run", "outside"),
        site(8, "m", "src/x.d:Thing.m")]


def test_every_verdict_of_an_added_typed_edge(written):
    a = analyse(written, [], ADDED, ROWS)
    assert len(a.added) == 6
    assert dict(a.added_verdicts) == {"agrees": 1, "checker: another declaration": 1, "no checker site": 1, "checker: none": 1,
                                      "checker: outside": 1, "agrees (via .d.ts pair)": 1}


def test_an_edge_by_name_or_made_in_a_python_file_is_not_a_typed_edge_of_the_change(written):
    a = analyse(written, [], ADDED, ROWS)
    assert {(c["line"], c["strategy"]) for c in a.added} == {(3, "receiver-type"), (4, "receiver-type"), (5, "receiver-type"),
                                                            (6, "inherited"), (7, "receiver-type"), (8, "receiver-type-ambiguous")}


def test_a_call_made_in_a_js_file_counts_like_one_made_in_a_ts_file(written):
    a = analyse(written, [], [call(JS_MAIN, FOO, 3, "receiver-type")], [{"file": "src/app.js", "line": 3, "method": "run", "declared": ["src/a:Foo.run"]}])
    assert [c["caller_id"] for c in a.added] == [JS_MAIN["id"]] and dict(a.added_verdicts) == {"agrees": 1}


def test_an_edge_the_base_already_had_is_not_added(written):
    a = analyse(written, [call(MAIN, FOO, 3, "receiver-type")], ADDED, ROWS)
    assert len(a.added) == 5 and "agrees" not in a.added_verdicts


def test_a_dropped_by_name_edge_is_replaced_when_the_site_keeps_an_edge_to_a_method_of_that_name_and_lost_when_it_keeps_none(written):
    before = [call(MAIN, BAR, 12, "name"), call(MAIN, ONLY, 14, "name"), call(PY_MAIN, FOO, 15, "name")]
    after = [call(MAIN, FOO, 12, "receiver-type")]  # a typed edge to another `run` at line 12; nothing at 14
    rows = [site(12, "run", "src/a:Foo.run"), site(14, "lone")]
    a = analyse(written, before, after, rows)
    assert len(a.dropped) == 2
    assert dict(a.fate) == {("replaced", "checker: another declaration"): 1, ("lost", "checker: none"): 1}


def test_an_edge_both_trees_have_is_not_dropped(written):
    kept = call(MAIN, BAR, 20, "name")
    a = analyse(written, [kept, call(MAIN, ONLY, 21, "name")], [kept], [site(20, "run", "src/b:Bar.run")])
    assert [c["line"] for c in a.dropped] == [21]


def test_a_dropped_edge_to_a_declaration_file_the_checker_gives_as_the_js_beside_it_agrees(written):
    a = analyse(written, [call(MAIN, THING, 22, "name")], [], [site(22, "m", "src/x.d:Thing.m")])
    assert dict(a.dropped_verdicts) == {"agrees (via .d.ts pair)": 1}
    assert tool.share(a.dropped_verdicts, "agrees", "agrees (via .d.ts pair)") == (1, 1, 100.0)
    assert any("the checker agrees with the callee 1 (100.00 %)" in line for line in tool.report("r", a, 0, 7))


def test_the_percentages_count_only_the_sites_the_checker_has(written):
    a = analyse(written, [], ADDED, ROWS)
    assert tool.share(a.added_verdicts, "agrees", "agrees (via .d.ts pair)") == (2, 5, 40.0)
    assert tool.share(a.added_verdicts, "agrees")[0] == 1


def test_a_declaration_file_stands_for_the_js_beside_it():
    assert tool.pair("src/x.d:Thing.m") == "src/x:Thing.m" and tool.pair("src/x:Thing.m") == "src/x:Thing.m"


def test_the_checker_key_of_a_symbol_and_of_a_file_caller_is_the_path_without_the_extension():
    assert tool.path_of(f"{P}/sym/src/a:Foo.run#method") == "src/a"
    assert tool.path_of(f"{P}/file/src/use.ts") == "src/use"


def test_the_report_has_the_lines_the_judgment_reads(written):
    b, a, c = written([call(MAIN, BAR, 12, "name")], ADDED, ROWS)
    out = tool.report("r", tool.Analysis(tool.load(b, "r"), tool.load(a, "r"), tool.checker_sites(c)), 0, 7)
    assert out[0].startswith("r typed edges the change adds: 6")
    assert any("added with a checker site: 5, agree 2 (40.0 %" in line for line in out)
    assert any("dropped with a checker site" in line for line in out) and any("lost" in line for line in out)


def test_a_sample_lists_the_added_edges_where_the_checker_names_another_declaration(written, capsys):
    b, a, c = written([], ADDED, ROWS)
    assert tool.main(["r", b, a, c, "--sample", "3", "--seed", "1"]) == 0
    out = capsys.readouterr().out
    assert "1 added typed edges where the checker names another declaration" in out
    assert "src/use:4 [receiver-type] -> src/b:Bar.run; the checker: ['src/a:Foo.run']" in out


def test_a_sample_is_the_same_for_one_seed_and_a_sample_is_no_longer_than_the_rows(written, capsys):
    calls = [call(MAIN, edge, 30 + i, "receiver-type") for i, edge in enumerate(MANY)]
    rows = [site(30 + i, "go", "src/b:Bar.run") for i in range(8)]  # the checker names another declaration for every one
    b, a, c = written([], calls, rows)
    picked = []
    for _ in range(2):
        tool.main(["r", b, a, c, "--sample", "4", "--seed", "5"])
        picked.append([line for line in capsys.readouterr().out.splitlines() if line.startswith("  src/use:")])
    assert picked[0] == picked[1] and len(picked[0]) == 4
    tool.main(["r", b, a, c, "--sample", "50"])
    assert len([l for l in capsys.readouterr().out.splitlines() if l.startswith("  src/use:")]) == 8


def test_without_the_four_arguments_it_prints_its_usage_and_ends_with_2(capsys):
    assert tool.main(["r", "a"]) == 2
    assert "ts_vs_checker.py REPO BEFORE_DIR AFTER_DIR CHECKER.jsonl" in capsys.readouterr().err
