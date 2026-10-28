#!/usr/bin/env python3
"""The type a tree's code gives each name a method is called on, in the Go files of the given repos: one JSON line per
call on a name, or on a chain of fields from one, that the code types (repo, file, line, receiver, type, closures,
src). `closures` counts the function literals around the use, a fact for a case table. Run once per tree to compare, with
that tree's `indexer/` on PYTHONPATH, and give both files to `attribution.py`. In the indexer's image.

    go_answers.py REPOS_DIR REPO... > ANSWERS.jsonl

The vendor folder and .git are not read."""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

from tree_sitter_language_pack import get_parser

SKIP = {".git", "vendor"}


def _walk(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode(errors="replace")


def _closures(node) -> int:
    count, parent = 0, node.parent
    while parent is not None:
        count += parent.type == "func_literal"
        parent = parent.parent
    return count


def go_files(base: Path):
    for directory, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        for name in sorted(f for f in files if f.endswith(".go")):
            yield Path(directory) / name


def calls_on_names(root, src: bytes, typer):
    """(call, the name it starts from, the fields after it) for each method call on a name or a chain from one."""
    for node in _walk(root):
        fn = node.child_by_field_name("function") if node.type == "call_expression" else None
        operand = fn.child_by_field_name("operand") if fn is not None and fn.type == "selector_expression" else None
        found = typer.receiver_chain(operand, src) if operand is not None else None
        if found is not None:
            yield node, found[0], found[1]


def survey(root, repo: str, typer, parser=None) -> tuple:
    """(the rows of the calls the code types, the number of calls on a name) for one repo."""
    parser, base, rows, sites = parser or get_parser("go"), Path(root) / repo, [], 0
    for path in go_files(base):
        src = path.read_bytes()
        lines = src.splitlines()
        for call, name, chain in calls_on_names(parser.parse(src).root_node, src, typer):
            sites += 1
            typ = typer.declared_type(_text(name, src), name, src)
            if typ is not None:
                line = call.start_point[0] + 1
                rows.append({"repo": repo, "file": str(path.relative_to(base)), "line": line,
                             "receiver": ".".join([_text(name, src), *chain]), "type": typ, "closures": _closures(name),
                             "src": lines[line - 1].decode(errors="replace").strip()[:160]})
    return rows, sites


def answers(root, repo: str, typer, parser=None) -> list:
    return survey(root, repo, typer, parser)[0]


def main(argv: list) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    typer = importlib.import_module("aidd_indexer.languages.go.locals")
    for repo in argv[1:]:
        rows, sites = survey(argv[0], repo, typer)
        for row in rows:
            print(json.dumps(row))
        print(f"{repo}: {len(rows)} typed of {sites} method calls on a name", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
