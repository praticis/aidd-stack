"""TS's scope index against TypeScript's own binder, over every TS and JS file the indexer extracts from the repos under
/corpus. Each name a file reads through its scopes must bind to the declarations of the file the binder gives it, for
what its place means (a value, a type or a namespace), and each `this` to the node that binds it. A name that binds to
no declaration of its file on either side is not compared: a global, a name another file or a package declares. A file
the compiler does not parse, or where tree-sitter finds an error, is counted apart; one where tree-sitter only supplies
a missing token is compared. Two kinds of difference are counted apart:
- `misread`, in code tree-sitter reads as other code: a generic tag of a template (`styled.div<Props>` before a
  template), which it reads as two comparisons, a `using` declaration, which it reads as an assignment, and a
  declaration written `let[a, b]` with no space, which it reads as an index into a variable `let`;
- `require`, a JS `const` a `require` initializes, which the binder binds as an import in the function around it, where
  JS binds it in its block.
The compiler reads and binds the files; nothing runs.

    ts_scopes.py [N]    N samples of each kind of difference (default 5)

In the image, with the code at /src, the compiler at $AIDD_TYPESCRIPT and the corpus's repos at /corpus."""
import collections
import codecs
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from aidd_indexer import languages
from aidd_indexer.core.discovery import language_of, list_files
from aidd_indexer.languages.typescript.scope_model import FIELDS
from aidd_indexer.languages.typescript.scopes import TsScopes

ORACLE = Path(__file__).with_name("ts_scopes.js")
TS = frozenset({"typescript", "tsx", "javascript"})
BATCH = 400


class Difference(NamedTuple):
    kind: str           # bound, missing, extra, this, misread or require
    at: str             # line:column, both from 0, the column in UTF-16 units
    name: str
    index: str
    compiler: str


class TreeError(Exception):
    pass


class Positions:
    """A node's place as the compiler writes it."""

    def __init__(self, src: bytes) -> None:
        self.lines = src.split(b"\n")
        self.bom = src.startswith(codecs.BOM_UTF8)

    def of(self, node: Node) -> str:
        row, col = node.start_point
        units = len(self.lines[row][:col].decode("utf-8", "replace").encode("utf-16-le")) // 2
        return f"{row}:{units - 1 if row == 0 and self.bom else units}"

    def before(self, at: str) -> str:
        """The text of a line before a place the compiler writes."""
        row, units = map(int, at.split(":"))
        units += 1 if row == 0 and self.bom else 0
        return self.lines[row].decode("utf-8", "replace").encode("utf-16-le")[:2 * units].decode("utf-16-le", "replace")


def oracle(root: Path, rels: list[str]) -> list[dict]:
    """The binder's answers for the files `rels` under `root`, read in one program."""
    out = subprocess.run(["node", "--max-old-space-size=4096", str(ORACLE), str(root)], input="\n".join(rels),
                         capture_output=True, text=True, check=True,
                         env={**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")})
    return [json.loads(line) for line in out.stdout.splitlines()]


def compare(src: bytes, grammar: str, theirs: dict) -> tuple[list[Difference], int, int]:
    """The differences between the index and the binder in one file, and how many names and `this` were compared.
    Raises `TreeError` on a file where tree-sitter finds an error."""
    tree = get_parser(grammar).parse(src)
    if _error(tree.root_node):
        raise TreeError
    index, at = TsScopes(tree.root_node, src), Positions(src)
    mine = {at.of(n): (n, tuple(sorted(at.of(d) for d in index.binding(n)))) for n in index.names()}
    bound = {p: (tuple(d), how) for p, d, how in theirs["names"]}
    out = [d for p in sorted(mine.keys() | bound.keys()) if (d := _name(at, p, mine.get(p), bound.get(p)))]
    mine_this = {at.of(n): _key(at, index.this_of(n)) for n in index.thises()}
    their_this = dict(theirs["this"])
    out += [Difference("this", p, "this", mine_this.get(p, ""), their_this.get(p, ""))
            for p in sorted(mine_this.keys() | their_this.keys()) if mine_this.get(p) != their_this.get(p)]
    return out, len(mine.keys() | bound.keys()), len(mine_this.keys() | their_this.keys())


def _error(root: Node) -> bool:
    """Whether tree-sitter found an error in the file, as opposed to a token it supplies."""
    stack = [root] if root.has_error else []
    while stack:
        n = stack.pop()
        if n.is_error:
            return True
        stack.extend(c for c in n.children if c.has_error)
    return False


def _name(at: Positions, p: str, mine: tuple | None, theirs: tuple | None) -> Difference | None:
    name, found = mine if mine is not None else (None, None)
    decls, how = theirs if theirs is not None else ((), "")
    if found == decls or (found is None and not decls):
        return None
    kind = "missing" if found is None else "extra" if theirs is None else "bound"
    kind = "require" if how == "require" else "misread" if _misread(at, name, decls) else kind
    text = name.text.decode(errors="replace") if name is not None else ""
    return Difference(kind, p, text, ",".join(found or ()), ",".join(decls))


def _misread(at: Positions, name: Node | None, decls: tuple[str, ...]) -> bool:
    """A name in a generic tag of a template or in its template, which tree-sitter reads as `(tag < T) > template`, or
    one a `using` declaration or a `let[` declares."""
    p = name.parent if name is not None else None
    while p is not None and not _generic_tag(p):
        p = p.parent
    if p is not None:
        return True
    return any(at.before(d).rstrip().endswith("using") or re.search(r"\blet\[[^\]]*$", at.before(d)) for d in decls)


def _generic_tag(n: Node) -> bool:
    """`tag<T>` before a template, which tree-sitter closes early: as `(tag < T) > template`, the comparison possibly
    closing what is left of `>` (`(x) => sql < T`), or as an arrow function whose body is `tag<T>`, called with the
    template (`((x) => sql<T>)` before it)."""
    if n.type == "call_expression" and getattr(n.child_by_field_name("arguments"), "type", "") == "template_string":
        f = n.child_by_field_name("function")
        return f.type == "arrow_function" and f.child_by_field_name("body").type == "instantiation_expression"
    if n.type != "binary_expression" or _operator(n) != ">" or n.child_by_field_name("right").type != "template_string":
        return False
    left = n.child_by_field_name("left")
    while left is not None and not (left.type == "binary_expression" and _operator(left) == "<"):
        left = left.named_children[-1] if left.named_child_count else None
    return left is not None


def _operator(n: Node) -> str:
    op = n.child_by_field_name("operator")
    return op.type if op is not None else ""


def _key(at: Positions, binder: Node | None) -> str:
    """Where the node that binds a `this` starts its body or its initializer, as the oracle writes it."""
    if binder is None:
        return ""
    if binder.type == "program":
        return "program"
    start = binder.child_by_field_name("value" if binder.type in FIELDS else "body")
    return at.of(start) if start is not None else f"{binder.type}@{at.of(binder)}"


def counted(counts: collections.Counter, samples: dict, n: int, kind: str, line: str) -> None:
    counts[kind] += 1
    if len(samples[kind]) < n:
        samples[kind].append(line)


def check(repo: Path, counts: collections.Counter, samples: dict, n: int) -> None:
    rels = [r for r in list_files(repo) if language_of(PurePosixPath(r).suffix) in TS]
    for start in range(0, len(rels), BATCH):
        for theirs in oracle(repo, rels[start:start + BATCH]):
            rel = theirs["file"]
            counts["files"] += 1
            if theirs["broken"]:
                counted(counts, samples, n, "files the compiler does not parse", f"{repo.name}/{rel}")
                continue
            grammar = languages.by_extension(PurePosixPath(rel).suffix).grammar
            try:
                found, names, thises = compare((repo / rel).read_bytes(), grammar, theirs)
            except TreeError:
                counted(counts, samples, n, "files where tree-sitter finds an error", f"{repo.name}/{rel}")
                continue
            counts["files compared"] += 1
            counts["names compared"] += names
            counts["this compared"] += thises
            for d in found:
                counted(counts, samples, n, d.kind,
                        f"{repo.name}/{rel}:{d.at} {d.name!r} index={d.index} compiler={d.compiler}")


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 5
    counts: collections.Counter = collections.Counter()
    samples = collections.defaultdict(list)
    for repo in sorted(p for p in Path("/corpus").iterdir() if p.is_dir()):
        check(repo, counts, samples, n)
        print(f"{repo.name}: {counts['files']} files so far", file=sys.stderr, flush=True)
    for key, value in counts.items():
        print(f"{key}: {value}")
    for kind, lines in sorted(samples.items()):
        print(f"\n{kind}:\n  " + "\n  ".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
