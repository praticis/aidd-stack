"""The dry-runs, the checker's rows and the bounds the scorecard's tests are made of: one TS repo `r` whose calls have each a
verdict of the checker, in a file of the tree, and a Python call that is no TS call."""
import gzip
import json

P = "t/r@main"


def sym(path, qual, kind="method", ext=".ts"):
    return {"id": f"{P}/sym/{path}:{qual}#{kind}", "file_id": f"{P}/file/{path}{ext}", "qualified_name": f"{path}:{qual}"}


def file(path, ext=".ts"):
    return {"id": f"{P}/file/{path}{ext}", "path": f"{path}{ext}", "language": "typescript"}


def call(caller, callee, line, strategy, method=None):
    return {"caller_id": caller["id"], "callee_id": callee["id"], "line": line, "strategy": strategy, "method": method}


MAIN = sym("src/use", "main", "function")
PY_MAIN = sym("tools/run", "main", "function", ".py")
FOO, BAR, THING, ONLY = sym("src/a", "Foo.run"), sym("src/b", "Bar.run"), sym("src/x", "Thing.m"), sym("src/c", "Only.lone")
OWNER = sym("src/a", "Foo", "interface")  # the type that owns a member with no symbol
IMPL = sym("src/impl", "Impl.get")        # what runs where the checker names the member of a declaration file
SYMBOLS = [MAIN, PY_MAIN, FOO, BAR, THING, ONLY, OWNER, IMPL]
FILES = [file("src/use"), file("tools/run", ".py"), *[file(p) for p in ("src/a", "src/b", "src/x", "src/c", "src/impl")]]

CALLS = [
    call(MAIN, FOO, 3, "receiver-type", "run"),                # confirmed: the checker names Foo.run
    call(MAIN, BAR, 4, "receiver-type", "run"),                # contradicted: the checker names Foo.run
    call(MAIN, OWNER, 5, "inherited", "get"),                  # confirmed: the type that owns Foo.get, which has no symbol
    call(MAIN, IMPL, 6, "receiver-type", "get"),               # indirect: the checker names a declaration file's member
    call(MAIN, FOO, 7, "receiver-type-ambiguous", "run"),      # confirmed, and counted with receiver-type
    call(MAIN, ONLY, 8, "receiver-type", "lone"),              # undecided: no row
    call(MAIN, THING, 9, "unique-name", "m"),                  # by name, to the declaration the checker names
    call(MAIN, BAR, 10, "same-module-ambiguous", "run"),       # by name, to another declaration
    call(MAIN, FOO, 11, "receiver-type", "run"),               # undecided: the checker has no declaration
    call(PY_MAIN, FOO, 12, "receiver-type", "run"),            # made in a Python file
]
ROWS = [{"file": "src/use.ts", "line": n, "method": m, "declared": d} for n, m, d in (
    (3, "run", ["src/a:Foo.run"]), (4, "run", ["src/a:Foo.run"]), (5, "get", ["src/a:Foo.get"]), (6, "get", ["src/x.d:Iface.get"]),
    (7, "run", ["src/a:Foo.run"]), (9, "m", ["src/x:Thing.m"]), (10, "run", ["src/a:Foo.run"]), (11, "run", []))]


def dry_run(calls):
    return {"files": FILES, "symbols": SYMBOLS, "calls": calls}


def make_tree(tmp_path):
    def make(calls=CALLS, rows=ROWS, repo="r", name="runs"):
        runs = tmp_path / name
        runs.mkdir(exist_ok=True)
        with gzip.open(runs / f"{repo}.json.gz", "wt") as out:
            json.dump(dry_run(calls), out)
        rows_dir = tmp_path / "rows"
        rows_dir.mkdir(exist_ok=True)
        if rows is not None:
            (rows_dir / f"checker-{repo}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        return runs, rows_dir
    return make


BOUNDS = """# bounds
r.receiver-type.confirmed :: >= 2 :: a note
r.receiver-type.contradicted :: <= 1 :: a note
r.inherited.confirmed :: >= 1 :: a note
r.inherited.contradicted :: <= 0 :: a note
"""
