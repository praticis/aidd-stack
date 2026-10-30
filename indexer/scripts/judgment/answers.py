#!/usr/bin/env python3
"""What a tree answers about each method call's receiver, in one language's files of the given repos: the type its
extraction records, or the reason it gives for none, and what its resolver makes of the receiver before it looks at a
method. One JSON line per call on a receiver with any answer (repo, file, line, receiver, type, unknown, resolved, the
language's facts, src). The files, the calls and the answers are the tree's own: its discovery and extraction, its
query, `CallInfo.receiver_type` and `receiver_unknown`, and the questions its resolver asks, in the resolver's context.
Run once per tree to compare, with that tree's `indexer/` on PYTHONPATH, and give both files to `attribution.py`. In
the indexer's image.

    answers.py LANG REPOS_DIR REPO... > ANSWERS.jsonl

LANG is a language's id (go, python, ...). `resolved` is, in the resolver's order: `builtin`, a runtime builtin;
`package`, a name an import binds to a package; `type <name>`, the repo's type `LanguageSupport.resolve_receiver`
gives; `outside <name>`, what `external_receiver` names outside the repo; or null, a receiver the resolver goes by name
on. The fact a case table reads, `closures`, counts the function literals around the use: Go's func literals; Python's
lambdas and the functions defined in another function. A file the tree cannot extract is left out, as the dry-run
leaves it, and its warning goes to stderr."""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

from tree_sitter import QueryCursor

import aidd_indexer
from aidd_indexer import languages
from aidd_indexer.core.discovery import build_files, discover_modules, list_files
from aidd_indexer.core.extract import extract_file
from aidd_indexer.core.model import ExtractionResult, RepoInfo
from aidd_indexer.core.resolve import BUILTIN_RECEIVERS, Resolver
from aidd_indexer.core.types import RepoTypes


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


def resolved(rv: Resolver, lang, file, call) -> str | None:
    """What the resolver makes of a call's receiver before it looks at a method, asked as the resolver asks it."""
    root = re.split(r"[.(\[]", call.receiver, 1)[0].strip()
    if root in BUILTIN_RECEIVERS:
        return "builtin"
    if root in rv.external_bindings.get(call.file_id, ()):
        return "package"
    if not call.receiver_type:
        return None
    found = lang.resolve_receiver(rv.ctx, file, call.receiver_type, call.receiver_path)
    if found:
        return f"type {found}"
    outside = lang.external_receiver(rv.ctx, file, call.receiver_type, call.receiver_path)
    return f"outside {outside[0]}" if outside else None


def rows_of(name: str, fx, facts: dict, answer) -> list:
    nodes = call_nodes(fx)
    if len(nodes) != len(fx.calls) or any(n.start_point[0] + 1 != c.line for c, (n, _) in zip(fx.calls, nodes)):
        raise ProbeError(f"{name}/{fx.file.path}: the query's calls are not the ones the extractor recorded")
    lines, rows = fx.src.splitlines(), []
    for call, (_, receiver) in zip(fx.calls, nodes):
        found = answer(call) if call.receiver else None
        if call.receiver_type or call.receiver_unknown or found:
            rows.append({"repo": name, "file": fx.file.path, "line": call.line, "receiver": call.receiver,
                         "type": call.receiver_type, "unknown": call.receiver_unknown, "resolved": found,
                         **{k: fact(receiver) for k, fact in facts.items()},
                         "src": lines[call.line - 1].decode(errors="replace").strip()[:160]})
    return rows


def resolver(repo: RepoInfo, modules: list, files: list, extractors: list) -> Resolver:
    """The resolver over the language's files as the pipeline builds it, with the imports resolved. A language's
    answers read its own files' facts and imports only, so the other languages and the HTTP pass are left out."""
    res = ExtractionResult(repo=repo, modules=modules, files=files)
    for fx in extractors:
        res.symbols.extend(fx.symbols)
        res.calls.extend(fx.calls)
        res.imports.extend(fx.imports)
    res.types = RepoTypes.of_files(repo.root, files, modules, {fx.file.id: fx.facts for fx in extractors})
    rv = Resolver(res, extractors)
    rv.resolve_imports()
    return rv


def survey(root, name: str, lang: str) -> tuple:
    """(the rows of the calls on a receiver the tree answers about, the number of method calls on a receiver) in one
    repo."""
    repo = RepoInfo(tenant="probe", name=name, ref="probe", commit_sha="probe", root=str(Path(root) / name))
    rel = list_files(Path(repo.root))
    modules = discover_modules(repo, rel)[0]
    files = build_files(repo, rel, modules)
    extractors = []
    for file in (f for f in files if f.language == lang):
        fx, warnings = extract_file(repo, file)
        for warning in warnings:
            print(f"{name}: {warning}", file=sys.stderr)
        if fx is not None:
            extractors.append(fx)
    rv, language, rows, calls = resolver(repo, modules, files, extractors), languages.by_id(lang), [], 0
    for fx in extractors:
        calls += sum(c.receiver is not None for c in fx.calls)
        rows += rows_of(name, fx, FACTS.get(lang, {}), lambda c, f=fx.file: resolved(rv, language, f, c))
    return rows, calls


def counts(repo: str, rows: list, calls: int) -> str:
    typed = sum(row["type"] is not None for row in rows)
    reasons = sum(row["type"] is None and row["unknown"] is not None for row in rows)
    kinds = collections.Counter(row["resolved"].split(" ", 1)[0] for row in rows if row["resolved"])
    kinds["by name"] = calls - sum(kinds.values())
    return (f"{repo}: {typed} typed of {calls} method calls on a receiver, {reasons} untyped with a reason; the "
            "resolver: " + ", ".join(f"{kinds[k]} {k}" for k in ("type", "outside", "package", "builtin", "by name")))


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
            print(counts(repo, rows, calls), file=sys.stderr)
    except ProbeError as e:
        print(f"answers: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
