"""Python's scope index against CPython's own symbol table, over every Python file under /corpus. Each scope the index
builds is paired with symtable's by kind, line and order, and each name the scope binds or reads must be classified
the same: local, global or free.

CPython 3.12 inlines a list, set or dict comprehension into the scope around it (PEP 709), so its table no longer
shows the comprehension's own scope; the rules are still a generator expression's. The source symtable reads has each
of them written as a generator expression, on the same lines. symtable only compiles a file's symbols: nothing runs.
A file CPython 3.12 does not compile (Python 2, or a later Python's syntax such as 3.14's `except A, B:`) or that
tree-sitter does not parse is counted apart.

    python_scopes.py [N]    N samples of each kind of difference (default 5)

In the image, with the code at /src and the corpus's repos at /corpus."""
import ast
import collections
import symtable
import sys
from pathlib import Path
from typing import NamedTuple

from tree_sitter_language_pack import get_parser

from aidd_indexer.languages.python.scopes import PyScopes, Scope

PARSER = get_parser("python")
# names the compiler adds to methods and classes, unless the source binds them too
IMPLICIT = {"__class__", "__classdict__", "__type_params__"}


class Difference(NamedTuple):
    kind: str           # scope, missing, extra or classified
    line: int
    name: str
    index: str
    cpython: str


class TreeError(Exception):
    pass


def as_generators(text: str) -> str:
    """The source with each list, set and dict comprehension written as a generator expression, on the same lines."""
    raw = text.encode()
    starts = [0]
    for line in raw.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    edits = []
    for n in ast.walk(ast.parse(text)):
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp)):
            edits += [(starts[n.lineno - 1] + n.col_offset, 1, b"("),
                      (starts[n.end_lineno - 1] + n.end_col_offset - 1, 1, b")")]
        if isinstance(n, ast.DictComp):
            key_end = starts[n.key.end_lineno - 1] + n.key.end_col_offset
            edits += [(starts[n.key.lineno - 1] + n.key.col_offset, 0, b"("), (raw.index(b":", key_end), 1, b","),
                      (starts[n.value.end_lineno - 1] + n.value.end_col_offset, 0, b")")]
    # from the end, and a replacement before an insertion at the same place
    for at, length, new in sorted(edits, reverse=True):
        raw = raw[:at] + new + raw[at + length:]
    return raw.decode()


def kind_of(table) -> str:
    kind = table.get_type()
    return kind if kind in ("module", "class", "function") else "annotation"


def compare(src: bytes) -> list[Difference]:
    """The differences between the index and symtable in one file. Raises what CPython raises on a file it cannot
    compile, and `TreeError` on one tree-sitter cannot parse."""
    table = symtable.symtable(as_generators(src.decode()), "file", "exec")
    tree = PARSER.parse(src)
    if tree.root_node.has_error:
        raise TreeError
    out: list[Difference] = []
    index = PyScopes(tree.root_node, src)
    _pair(index, index.module, table, None, out)
    return out


def _pair(index: PyScopes, scope: Scope, table, cls: str | None, out: list) -> None:
    cls = table.get_name() if table.get_type() == "class" else cls
    out += _names(index, scope, table, cls)
    theirs = collections.defaultdict(collections.deque)
    for t in table.get_children():
        theirs[(kind_of(t), t.get_lineno())].append(t)
    for s in sorted(scope.children, key=lambda s: s.node.start_byte):
        key = ("function" if s.kind == "comprehension" else s.kind, s.node.start_point[0] + 1)
        if theirs[key]:
            # scopes on one line are not in the source's order: what a definition or a comprehension reads around it
            # is compiled before it, so a scope is paired with the table whose names are most like its own
            names = {*s.bindings, *s.uses}
            match = max(theirs[key], key=lambda t: len(names & {x.get_name() for x in t.get_symbols()}))
            theirs[key].remove(match)
            _pair(index, s, match, cls, out)
        else:
            out.append(Difference("scope", key[1], "", s.kind, ""))
    out += [Difference("scope", line, "", "", kind) for (kind, line), ts in theirs.items() for _ in ts]


def _names(index: PyScopes, scope: Scope, table, cls: str | None) -> list[Difference]:
    theirs = {}
    for s in table.get_symbols():
        name = _unmangled(s.get_name(), cls)
        if not name.startswith("."):
            theirs[name] = "local" if s.is_local() else "global" if s.is_global() else "free" if s.is_free() else "?"
    names = {*scope.bindings, *scope.uses, *scope.globals, *scope.nonlocals}
    mine = {name: _kind(index, scope, name) for name in names}
    for name in _passing(index, scope):
        mine.setdefault(name, "free")
    theirs = {n: k for n, k in theirs.items() if n not in IMPLICIT or n in mine}
    if scope.kind == "module":
        # the module's table lists the names a function declares global, and its own names are its globals
        mine.update({n: "global" for s in index.scopes for n in s.globals if n not in mine})
        theirs = {n: "global" if k == "local" else k for n, k in theirs.items()}
        mine = {n: "global" if k == "local" else k for n, k in mine.items()}
    line = scope.node.start_point[0] + 1
    return [Difference("missing", line, n, "", theirs[n]) for n in sorted(theirs.keys() - mine.keys())] + \
        [Difference("extra", line, n, mine[n], "") for n in sorted(mine.keys() - theirs.keys())] + \
        [Difference("classified", line, n, mine[n], theirs[n]) for n in sorted(mine.keys() & theirs.keys())
         if mine[n] != theirs[n]]


def _kind(index: PyScopes, scope: Scope, name: str) -> str:
    """symtable calls a name the module binds local to it."""
    if scope.kind == "module" and name in scope.bindings and name not in scope.globals:
        return "local"
    return index.resolve(scope, name).kind


def _passing(index: PyScopes, scope: Scope) -> set[str]:
    """The names a scope inside this one reads from a function outside it: the compiler passes each through this
    scope, whose table lists it as free."""
    out, stack = set(), list(scope.children)
    while stack:
        s = stack.pop()
        stack.extend(s.children)
        for name in {*s.uses, *s.bindings, *s.nonlocals}:
            b = index.resolve(s, name)
            if b.kind == "free" and _outside(b.scope, scope):
                out.add(name)
    return out


def _outside(owner: Scope | None, scope: Scope) -> bool:
    s = scope.parent
    while s is not None:
        if s is owner:
            return True
        s = s.parent
    return False


def _unmangled(name: str, cls: str | None) -> str:
    """`_C__x` in a class `C` and the scopes inside it is the source's `__x`."""
    prefix = f"_{(cls or '').lstrip('_')}__"
    return name[len(prefix) - 2:] if cls and cls.lstrip("_") and name.startswith(prefix) else name


def counted(counts: collections.Counter, samples: dict, n: int, kind: str, line: str) -> None:
    counts[kind] += 1
    if len(samples[kind]) < n:
        samples[kind].append(line)


def check(f: Path, counts: collections.Counter, samples: dict, n: int) -> None:
    rel = f.relative_to("/corpus")
    try:
        found = compare(f.read_bytes())
    except (SyntaxError, ValueError, UnicodeDecodeError, RecursionError) as e:
        counted(counts, samples, n, "files CPython 3.12 does not compile", f"{rel}: {e}")
        return
    except TreeError:
        counted(counts, samples, n, "files tree-sitter does not parse", str(rel))
        return
    counts["files compared"] += 1
    for d in found:
        counted(counts, samples, n, d.kind, f"{rel}:{d.line} {d.name!r} index={d.index} cpython={d.cpython}")


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 5
    counts: collections.Counter = collections.Counter()
    samples = collections.defaultdict(list)
    for f in sorted(p for repo in sorted(Path("/corpus").iterdir()) for p in repo.rglob("*.py")):
        if f.is_file() and not f.is_symlink():
            counts["files"] += 1
            check(f, counts, samples, n)
    for key, value in counts.items():
        print(f"{key}: {value}")
    for kind, lines in sorted(samples.items()):
        print(f"\n{kind}:\n  " + "\n  ".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
