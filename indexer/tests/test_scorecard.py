"""The scorecard of a tree's graph against its references (scripts/judgment/scorecard.py), on dry-runs and checker rows made for
the purpose: the mix, the four numbers against the checker, the floors that judge them, and the exit codes."""
import gzip
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("scorecard", Path(__file__).resolve().parent.parent / "scripts" / "judgment" / "scorecard.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

P = "t/r@main"


def sym(path, qual, kind="method"):
    return {"id": f"{P}/sym/{path}:{qual}#{kind}", "file_id": f"{P}/file/{path}.ts", "qualified_name": f"{path}:{qual}"}


def file(path, ext=".ts"):
    return {"id": f"{P}/file/{path}{ext}", "path": f"{path}{ext}", "language": "typescript"}


def call(caller, callee, line, strategy, method=None):
    return {"caller_id": caller["id"], "callee_id": callee["id"], "line": line, "strategy": strategy, "method": method}


MAIN = sym("src/use", "main", "function")
PY_MAIN = {"id": f"{P}/sym/tools/run:main#function", "file_id": f"{P}/file/tools/run.py", "qualified_name": "tools/run:main"}
FOO, BAR, THING, ONLY = sym("src/a", "Foo.run"), sym("src/b", "Bar.run"), sym("src/x", "Thing.m"), sym("src/c", "Only.lone")
OWNER = sym("src/a", "Foo", "interface")  # the type that owns a member with no symbol
OTHER = sym("src/other", "go", "function")
SYMBOLS = [MAIN, PY_MAIN, FOO, BAR, THING, ONLY, OWNER, OTHER]
FILES = [file("src/use"), file("tools/run", ".py"), file("src/a"), file("src/b"), file("src/x"), file("src/c"), file("src/other")]

CALLS = [
    call(MAIN, FOO, 3, "receiver-type", "run"),        # the checker agrees
    call(MAIN, BAR, 4, "receiver-type", "run"),        # the checker names Foo
    call(MAIN, OWNER, 5, "inherited", "get"),          # the checker names a member of the type: another declaration
    call(MAIN, ONLY, 6, "receiver-type", "lone"),      # no row: not judged
    call(MAIN, THING, 7, "unique-name", "m"),          # by name, to the declaration the checker names
    call(PY_MAIN, FOO, 8, "receiver-type", "run"),     # made in a Python file
]
ROWS = [{"file": "src/use.ts", "line": n, "method": m, "declared": [d]} for n, m, d in
        ((3, "run", "src/a:Foo.run"), (4, "run", "src/a:Foo.run"), (5, "get", "src/a:Foo.get"), (7, "m", "src/x:Thing.m"))]


def dry_run(calls):
    return {"files": FILES, "symbols": SYMBOLS, "calls": calls}


@pytest.fixture
def tree(tmp_path):
    def make(calls=CALLS, rows=ROWS, repo="r"):
        runs = tmp_path / "runs"
        runs.mkdir(exist_ok=True)
        with gzip.open(runs / f"{repo}.json.gz", "wt") as out:
            json.dump(dry_run(calls), out)
        rows_dir = tmp_path / "rows"
        rows_dir.mkdir(exist_ok=True)
        if rows is not None:
            (rows_dir / f"checker-{repo}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        return runs, rows_dir
    return make


def numbers(metrics):
    return {m.name: (round(m.value, 1), m.hit, m.of) for m in metrics}


def test_the_mix_is_the_share_of_calls_a_type_decided(tree):
    runs, _ = tree()
    m = {m.name: m for m in S.measure(runs, None)}
    assert numbers(m.values()) == {"r.typed-share": (83.3, 5, 6)}  # five of the six calls are typed, the Python one too


def test_a_repo_with_no_rows_has_only_the_mix_and_each_dry_run_is_a_repo(tree):
    runs, rows = tree(rows=None)
    tree(repo="a", rows=None)
    assert [m.name for m in S.measure(runs, rows)] == ["a.typed-share", "r.typed-share"]


def test_the_numbers_against_the_checker(tree):
    runs, rows = tree()
    got = numbers(S.measure(runs, rows))
    assert got["r.keyed"] == (100.0, 5, 5)                 # the five TS calls, all in a file with rows; the Python call is no TS call
    assert got["r.typed-precision"] == (33.3, 1, 3)        # three typed edges at a site the checker judges, one agrees
    assert got["r.recall"] == (50.0, 2, 4)                 # of four sites the checker decides, two have an edge to the declaration
    assert got["r.typed-recall"] == (25.0, 1, 4)           # and one of them by a typed edge: the by-name one is not


def test_an_edge_to_the_type_that_owns_a_member_is_judged_by_the_method_it_records(tree):
    runs, rows = tree(calls=[call(MAIN, OWNER, 5, "inherited", "get")], rows=ROWS[2:3])
    assert numbers(S.measure(runs, rows))["r.typed-precision"] == (0.0, 0, 1)


def test_a_declaration_file_stands_for_the_js_beside_it(tree):
    runs, rows = tree(calls=[call(MAIN, THING, 7, "receiver-type", "m")], rows=[{"file": "src/use.ts", "line": 7, "method": "m", "declared": ["src/x.d:Thing.m"]}])
    got = numbers(S.measure(runs, rows))
    assert got["r.typed-precision"] == (100.0, 1, 1) and got["r.recall"] == (100.0, 1, 1)


def test_a_declaration_outside_the_repo_is_no_decided_site(tree):
    runs, rows = tree(rows=[{"file": "src/use.ts", "line": 3, "method": "run", "declared": ["outside"]}])
    assert numbers(S.measure(runs, rows))["r.recall"] == (0.0, 0, 0)


FLOORS = """# floors
r.typed-share :: 83.33 :: a note
r.keyed :: 100.0 :: a note
r.typed-precision :: 33.33 :: a note
r.recall :: 50.0 :: a note
r.typed-recall :: 25.0 :: a note
"""


def statuses(metrics, floors=FLOORS, min_keyed=50.0):
    return {(m or f).name: status for status, m, f in S.judge(metrics, S.load_floors(floors), min_keyed)}


def test_every_number_at_its_floor_passes(tree):
    runs, rows = tree()
    assert set(statuses(S.measure(runs, rows)).values()) == {"ok"}


def test_a_number_a_hundredth_under_its_floor_is_below(tree):
    runs, rows = tree()
    assert statuses(S.measure(runs, rows), FLOORS.replace("r.recall :: 50.0", "r.recall :: 50.01"))["r.recall"] == "below"


def test_a_number_without_a_floor_and_a_floor_without_a_number_both_fail(tree):
    runs, rows = tree()
    got = statuses(S.measure(runs, rows), FLOORS.replace("r.recall ::", "r.other ::"))
    assert got["r.recall"] == "unfloored" and got["r.other"] == "not measured"


def test_when_the_keys_do_not_match_the_numbers_against_the_checker_are_invalid_and_the_mix_is_not(tree):
    runs, rows = tree(rows=[{**r, "file": "packages/" + r["file"]} for r in ROWS])
    got = statuses(S.measure(runs, rows), FLOORS.replace("r.keyed :: 100.0", "r.keyed :: 0.0"))
    assert got["r.typed-precision"] == got["r.recall"] == got["r.typed-recall"] == "invalid" and got["r.typed-share"] == "ok"


def test_a_floor_is_a_number_the_value_rounded_down_to_a_hundredth_passes():
    assert (S.rounded_down(84.857), S.rounded_down(100.0), S.rounded_down(100 / 3), S.rounded_down(0.0)) == (84.85, 100.0, 33.33, 0.0)
    assert S.rounded_down(99.99999999) == 100.0  # float noise is not a loss


@pytest.mark.parametrize("text", ["r.recall 50 :: a note", "r.recall :: 50", "R.recall :: 50 :: n", "recall :: 50 :: n", "r.recall :: fifty :: n",
                                  "r.recall :: 50 :: n\nr.recall :: 60 :: n", "r.recall ::  :: n"])
def test_a_wrong_list_of_floors_is_an_error_with_its_line(text):
    with pytest.raises(ValueError, match="line"):
        S.load_floors(text)


def test_a_comment_and_a_blank_line_are_no_floor():
    assert [f.name for f in S.load_floors("# a\n\nr.recall :: 50 :: a note\n   # b\n")] == ["r.recall"]


def test_a_note_may_hold_the_separator():
    assert S.load_floors("r.recall :: 50 :: a :: b")[0].note == "a :: b"


def test_the_report_says_each_number_its_denominator_its_floor_and_its_headroom(tree):
    runs, rows = tree()
    text = S.report(S.judge(S.measure(runs, rows), S.load_floors(FLOORS), 50.0))
    assert "| `r.recall` | 50.00 % | 2 of 4 | 50.00 % | +0.00 | ok |" in text
    assert "not ok" not in text


def test_the_report_of_a_number_under_its_floor_says_how_a_floor_is_lowered(tree):
    runs, rows = tree()
    text = S.report(S.judge(S.measure(runs, rows), S.load_floors(FLOORS.replace("r.recall :: 50.0", "r.recall :: 60.0")), 50.0))
    assert "| `r.recall` | 50.00 % | 2 of 4 | 60.00 % | -10.00 | below |" in text
    assert "1 number(s) not ok" in text and "`graph-change`" in text and "reference_floors.txt" in text


def test_main_ends_in_0_when_every_number_holds_and_in_1_when_one_does_not(tree, tmp_path, capsys):
    runs, rows = tree()
    floors = tmp_path / "floors.txt"
    floors.write_text(FLOORS)
    assert S.main([str(runs), "--rows", str(rows), "--floors", str(floors)]) == 0
    floors.write_text(FLOORS.replace("r.recall :: 50.0", "r.recall :: 50.01"))
    assert S.main([str(runs), "--rows", str(rows), "--floors", str(floors)]) == 1
    assert "below" in capsys.readouterr().out


def test_main_ends_in_2_for_a_wrong_list_a_missing_folder_or_an_unknown_option(tree, tmp_path, capsys):
    runs, rows = tree()
    bad = tmp_path / "bad.txt"
    bad.write_text("r.recall 50\n")
    assert S.main([str(runs), "--floors", str(bad)]) == 2
    assert S.main([str(runs), "--floors", str(tmp_path / "missing.txt")]) == 2
    assert S.main([str(runs), "--nope"]) == 2
    assert "scorecard.py RUN_DIR" in capsys.readouterr().err


def test_the_threshold_of_the_keys_is_an_option(tree, tmp_path):
    runs, rows = tree(rows=[ROWS[0]])  # the row of one site: all five TS calls are in its file, so the keys match
    floors = tmp_path / "f.txt"
    floors.write_text("\n".join(f"r.{n} :: 0.0 :: n" for n in ("typed-share", "keyed", "typed-precision", "recall", "typed-recall")))
    assert S.main([str(runs), "--rows", str(rows), "--floors", str(floors), "--min-keyed", "100"]) == 0
    assert S.main([str(runs), "--rows", str(tree(rows=[{**ROWS[0], "file": "x/use.ts"}])[1]), "--floors", str(floors), "--min-keyed", "1"]) == 1


def test_write_floors_prints_a_line_per_number_rounded_down_and_ends_in_0(tree, capsys):
    runs, rows = tree()
    assert S.main([str(runs), "--rows", str(rows), "--write-floors"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "r.typed-precision :: 33.33 :: measured on the base" in lines and "r.typed-share :: 83.33 :: measured on the base" in lines
    assert len(lines) == 5
    assert len(S.load_floors("\n".join(lines))) == 5  # what it prints is a list it reads back


def test_the_threshold_given_is_the_one_that_judges_the_keys(tree, tmp_path):
    calls = [call(MAIN, FOO, 3, "receiver-type", "run"), call(MAIN, FOO, 4, "receiver-type", "run"),
             *[call(OTHER, FOO, 10 + i, "receiver-type", "run") for i in range(3)]]  # two of five calls are in a file with rows: 40 %
    runs, rows = tree(calls=calls, rows=ROWS[:1])
    floors = tmp_path / "f.txt"
    floors.write_text("\n".join(f"r.{n} :: 0.0 :: n" for n in ("typed-share", "keyed", "typed-precision", "recall", "typed-recall")))
    assert S.main([str(runs), "--rows", str(rows), "--floors", str(floors)]) == 1                       # under the default 50
    assert S.main([str(runs), "--rows", str(rows), "--floors", str(floors), "--min-keyed", "30"]) == 0


def test_the_real_list_of_floors_loads_and_names_a_percent_of_a_repo_each():
    floors = S.load_floors((Path(__file__).resolve().parent.parent / "scripts" / "checks" / "reference_floors.txt").read_text())
    assert floors and all(0 <= f.floor <= 100 and f.note for f in floors)


def test_the_floors_a_change_lowers_are_the_ones_it_holds_under_the_base_and_nothing_else():
    base = S.load_floors("a.recall :: 50 :: n\nb.recall :: 60 :: n\nc.recall :: 70 :: n\nd.recall :: 80 :: n")
    now = S.load_floors("a.recall :: 49.99 :: n\nb.recall :: 60 :: n\nc.recall :: 71 :: n\ne.recall :: 1 :: n")  # d gone, e new
    assert S.lowered(base, now) == [("a.recall", 50.0, 49.99)]


def test_lowered_prints_a_line_per_floor_and_ends_in_0(tmp_path, capsys):
    base, now = tmp_path / "base.txt", tmp_path / "now.txt"
    base.write_text("a.recall :: 50 :: n\nb.recall :: 60 :: n\n")
    now.write_text("a.recall :: 40 :: n\nb.recall :: 60 :: n\n")
    assert S.main(["--lowered", str(base), str(now)]) == 0
    assert capsys.readouterr().out.splitlines() == ["a.recall 50.0 40.0"]
    now.write_text("a.recall :: 50 :: n\n")
    assert S.main(["--lowered", str(base), str(now)]) == 0 and capsys.readouterr().out.strip() == ""


def test_lowered_ends_in_2_for_a_wrong_list_a_missing_file_or_the_wrong_number_of_arguments(tmp_path, capsys):
    good, bad = tmp_path / "good.txt", tmp_path / "bad.txt"
    good.write_text("a.recall :: 50 :: n\n")
    bad.write_text("a.recall 50\n")
    assert S.main(["--lowered", str(good), str(bad)]) == 2
    assert S.main(["--lowered", str(good), str(tmp_path / "missing.txt")]) == 2
    assert S.main(["--lowered", str(good)]) == 2
    assert "--lowered BASE_FLOORS FLOORS" in capsys.readouterr().err

