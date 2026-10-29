#!/usr/bin/env python3
"""What a tree's extraction records as the type of each method call's receiver, in one language's files of the given
repos: one JSON line per call whose receiver the tree types, or gives a reason for not typing (repo, file, line,
receiver, type, unknown, the language's facts, src). The files, the calls and the types are the tree's own: its
discovery, its query, and `CallInfo.receiver_type` and `receiver_unknown`, which is what its resolver reads. Run once per tree to compare, with that tree's `indexer/` on PYTHONPATH, and give
both files to `attribution.py`. In the indexer's image.

    answers.py LANG REPOS_DIR REPO... > ANSWERS.jsonl

LANG is a language's id (go, python, ...). The fact a case table reads, `closures`, counts the function literals
around the use: Go's func literals; Python's lambdas and the functions defined in another function. A file the tree
cannot extract is left out, as the dry-run leaves it, and named on stderr."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from tree_sitter import QueryCursor

import aidd_indexer
from aidd_indexer import languages
from aidd_indexer.core.discovery import build_files, discover_modules, list_files
from aidd_indexer.core.extract import extract_file
from aidd_indexer.core.model import RepoInfo


class ProbeError(Exception):
    pass


def _ancestors(node):
    node = node.parent
    while node is not None:
        yield node
        node = node.parent


def _go_closures(node) -> int:
    return sum(a.type == "func_literal" for a in _ancestors(node))


def _python_closures(node) -> int:
    functions = [a for a in _ancestors(node) if a.type in ("function_definition", "lambda")]
    return len(functions) - (bool(functions) and functions[-1].type == "function_definition")


FACTS = {"go": {"closures": _go_closures}, "python": {"closures": _python_closures}}


def call_nodes(fx) -> list:
    """The (call, receiver) nodes of the calls the extractor records, in its order: the matches of the tree's own
    query that capture a call."""
    found = []
    for query, _ in fx.cl.patterns:
        for _, caps in QueryCursor(query).matches(fx.tree.root_node):
            if "call" in caps:
                found.append((caps["call"][0], caps.get("receiver", [None])[0]))
    return found


def rows_of(name: str, fx, facts: dict) -> list:
    nodes = call_nodes(fx)
    if len(nodes) != len(fx.calls) or any(n.start_point[0] + 1 != c.line for c, (n, _) in zip(fx.calls, nodes)):
        raise ProbeError(f"{name}/{fx.file.path}: the query's calls are not the ones the extractor recorded")
    lines, rows = fx.src.splitlines(), []
    for call, (_, receiver) in zip(fx.calls, nodes):
        if call.receiver_type or call.receiver_unknown:
            rows.append({"repo": name, "file": fx.file.path, "line": call.line, "receiver": call.receiver,
                         "type": call.receiver_type, "unknown": call.receiver_unknown,
                         **{k: fact(receiver) for k, fact in facts.items()},
                         "src": lines[call.line - 1].decode(errors="replace").strip()[:160]})
    return rows


def survey(root, name: str, lang: str) -> tuple:
    """(the rows of the calls the tree types, the number of method calls on a receiver) in one repo."""
    repo = RepoInfo(tenant="probe", name=name, ref="probe", commit_sha="probe", root=str(Path(root) / name))
    rel = list_files(Path(repo.root))
    files = [f for f in build_files(repo, rel, discover_modules(repo, rel)[0]) if f.language == lang]
    rows, calls = [], 0
    for file in files:
        fx, warnings = extract_file(repo, file)
        for warning in warnings:
            print(f"{name}: {warning}", file=sys.stderr)
        if fx is not None:
            calls += sum(c.receiver is not None for c in fx.calls)
            rows += rows_of(name, fx, FACTS.get(lang, {}))
    return rows, calls


def main(argv: list) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    lang, root, repos = argv[0], argv[1], argv[2:]
    if languages.by_id(lang) is None:
        print(f"answers: no language {lang}", file=sys.stderr)
        return 2
    print(f"aidd_indexer from {Path(aidd_indexer.__file__).parent}", file=sys.stderr)
    try:
        for repo in repos:
            rows, calls = survey(root, repo, lang)
            for row in rows:
                print(json.dumps(row))
            typed = sum(row["type"] is not None for row in rows)
            print(f"{repo}: {typed} typed of {calls} method calls on a receiver, {len(rows) - typed} untyped with a reason",
                  file=sys.stderr)
    except ProbeError as e:
        print(f"answers: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
