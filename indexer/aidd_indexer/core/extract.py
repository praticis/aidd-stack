"""tree-sitter extraction: symbols, call sites and imports per file.

Language queries live in `languages/<lang>/queries.scm`. Each blank-line-separated pattern is
compiled on its own so a pattern the installed grammar does not support is skipped (with a
warning) instead of disabling the language. Everything language-specific (qualified names,
visibility, docstrings, import bindings, entry-point markers) is delegated to the file's
`LanguageSupport` (see `languages/base.py`) — this module has no `if language == ...`.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from tree_sitter import Language, Node, Parser, Query, QueryCursor, QueryError
from tree_sitter_language_pack import get_language, get_parser

from .. import languages
from ..languages.base import LanguageSupport, node_text as _text, walk as _walk
from . import ids
from .model import CallInfo, FileInfo, ImportInfo, RepoInfo, SymbolInfo

# Symbol kinds that a call can target.
CALLABLE_KINDS = {"function", "method", "class", "struct"}


@dataclass
class CompiledLanguage:
    name: str
    language: Language
    parser: Parser
    patterns: list[tuple[Query, str]] = field(default_factory=list)  # (query, source)
    warnings: list[str] = field(default_factory=list)


GRAMMAR_ERRORS: dict[str, str] = {}   # language -> why it could not be loaded (surfaced by the CLI)

# tree-sitter-language-pack >= 1.x ships NO grammars in the wheel: `get_language()` downloads a
# prebuilt .so from GitHub Releases into TREE_SITTER_LANGUAGE_PACK_CACHE_DIR on first use.
# The indexer image prefetches every PARSEABLE grammar at build time (see indexer/Dockerfile) and
# sets AIDD_GRAMMAR_OFFLINE=1, so a run never depends on the network: a grammar missing from the
# cache is a broken image, reported immediately instead of after a download timeout.
GRAMMAR_OFFLINE = os.environ.get("AIDD_GRAMMAR_OFFLINE", "") not in ("", "0", "false")


def grammar_cached(grammar: str) -> bool:
    try:
        from tree_sitter_language_pack import downloaded_languages
        return grammar in set(downloaded_languages())
    except Exception:  # noqa: BLE001
        return False


@lru_cache(maxsize=None)
def load_language(name: str) -> CompiledLanguage | None:
    lang = languages.by_id(name)
    if lang is None:
        GRAMMAR_ERRORS[name] = "no language module registered"
        return None
    grammar = lang.grammar
    if GRAMMAR_OFFLINE and not grammar_cached(grammar):
        from tree_sitter_language_pack import cache_dir
        GRAMMAR_ERRORS[name] = (f"grammar '{grammar}' is not in the image cache ({cache_dir()}) and "
                                f"AIDD_GRAMMAR_OFFLINE is set — rebuild the indexer image")
        return None
    try:
        language = get_language(grammar)
        parser = get_parser(grammar)
    except Exception as e:  # noqa: BLE001
        GRAMMAR_ERRORS[name] = f"{type(e).__name__}: {e}"
        return None
    cl = CompiledLanguage(name=name, language=language, parser=parser)
    src_file = lang.query_file
    if not src_file.exists():
        return cl
    text = src_file.read_text(encoding="utf-8")
    # strip comment lines, split on blank lines
    blocks = re.split(r"\n\s*\n", "\n".join(l for l in text.splitlines() if not l.strip().startswith(";;")))
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        try:
            cl.patterns.append((Query(language, block), block))
        except QueryError as e:
            cl.warnings.append(f"{name}: skipped pattern ({str(e).splitlines()[0]}): {block[:60]}...")
    return cl


_ATTR_PREFIX = re.compile(r"^(\s*(\[[^\]]*\]|@[\w.]+(\([^)]*\))?)\s*)+")


def _first_line(node: Node, src: bytes, limit: int = 200) -> str:
    t = _ATTR_PREFIX.sub("", _text(node, src))
    for stop in ("{", "\n"):
        i = t.find(stop)
        if i > 0:
            t = t[:i]
    t = t.rstrip(" :=>")
    return " ".join(t.split())[:limit]


def _doc(node: Node, src: bytes, lang: LanguageSupport) -> str:
    parts: list[str] = []
    sib = node.prev_sibling
    while sib is not None and sib.type in ("comment", "line_comment", "block_comment", "decorator", "attribute_list"):
        if sib.type in ("comment", "line_comment", "block_comment"):
            parts.insert(0, _text(sib, src))
        sib = sib.prev_sibling
    parts += lang.doc_extra(node, src)
    doc = "\n".join(parts)
    doc = re.sub(r"^\s*(///?|/\*+|\*+/?|#|\"\"\"|''')\s?", "", doc, flags=re.M).strip()
    return doc[:1000]


def _leading_decorators(node: Node, src: bytes) -> str:
    """Decorators/attributes attached to a definition, wherever the grammar puts them."""
    texts: list[str] = []
    # TS: decorators are previous siblings inside class_body / program
    sib = node.prev_sibling
    while sib is not None and sib.type in ("decorator", "attribute_list", "comment"):
        if sib.type != "comment":
            texts.append(_text(sib, src))
        sib = sib.prev_sibling
    # TS: `export` wrapper — decorators sit before the export_statement
    if node.parent is not None and node.parent.type in ("export_statement", "decorated_definition"):
        sib = node.parent.prev_sibling
        while sib is not None and sib.type == "decorator":
            texts.append(_text(sib, src))
            sib = sib.prev_sibling
    # Python: decorated_definition wraps the def and holds decorators as children
    if node.parent is not None and node.parent.type == "decorated_definition":
        texts += [_text(c, src) for c in node.parent.children if c.type == "decorator"]
    # C#: attribute_list children of the declaration
    texts += [_text(c, src) for c in node.children if c.type == "attribute_list"]
    return "\n".join(texts)


def _entry_point(node: Node, src: bytes, signature: str, lang: LanguageSupport) -> bool:
    if any(h in signature for h in lang.entry_point_hints):
        return True
    if lang.decorator_entry is None:
        return False
    return bool(lang.decorator_entry.search(_leading_decorators(node, src)))


def _import_bindings(inode: Node, spec: str, src: bytes, lang: LanguageSupport) -> list[str]:
    """Local names introduced by the import statement that contains `inode`."""
    stmt = inode
    while stmt is not None and stmt.type not in ("import_statement", "import_spec", "import_from_statement",
                                                 "using_directive", "lexical_declaration", "expression_statement"):
        stmt = stmt.parent
    if stmt is None:
        return []
    return lang.import_bindings(_text(stmt, src), stmt, spec, src)


class FileExtractor:
    def __init__(self, repo: RepoInfo, file: FileInfo, src: bytes, cl: CompiledLanguage):
        self.repo, self.file, self.src, self.cl = repo, file, src, cl
        self.lang: LanguageSupport = languages.by_id(file.language)  # type: ignore[assignment]
        self.tree = cl.parser.parse(src)
        self.defs: dict[int, tuple[str, Node]] = {}   # def node id -> (kind, name node)
        self.symbol_by_node: dict[int, SymbolInfo] = {}
        self.symbols: list[SymbolInfo] = []
        self.calls: list[CallInfo] = []
        self.imports: list[ImportInfo] = []
        self.namespaces: list[str] = []                # namespaces declared in this file (C#)
        self.file_namespace: str | None = None         # file-scoped namespace — prefixes everything (C# `namespace X;`)
        self.seen_ids: set[str] = set()

    # -- pass 1: collect definitions ------------------------------------------------
    def run(self) -> None:
        raw_calls: list[tuple[Node, Node, Node | None]] = []   # (call node, callee name node, receiver)
        for query, _src in self.cl.patterns:
            for _pattern_idx, caps in QueryCursor(query).matches(self.tree.root_node):
                def_key = next((k for k in caps if k.startswith("def.")), None)
                if def_key:
                    kind = def_key.split(".", 1)[1]
                    dnode, nnode = caps[def_key][0], caps["name"][0]
                    # a more specific pattern (struct/interface) wins over generic `type`
                    prev = self.defs.get(dnode.id)
                    if prev is None or (prev[0] == "type" and kind != "type"):
                        self.defs[dnode.id] = (kind, nnode)
                    continue
                if "call" in caps:
                    raw_calls.append((caps["call"][0], caps["callee"][0], caps.get("receiver", [None])[0]))
                    continue
                if "import" in caps:
                    inode = caps["import"][0]
                    spec = _text(inode, self.src).strip("\"'`")
                    self.imports.append(ImportInfo(
                        file_id=self.file.id,
                        spec=spec,
                        line=inode.start_point[0] + 1,
                        bindings=_import_bindings(inode, spec, self.src, self.lang),
                    ))
        self.namespaces, self.file_namespace = self.lang.file_scope(self.tree.root_node, self.src)

        # materialize symbols outer-first so parents exist before children
        for dnode_id, (kind, nnode) in sorted(self.defs.items(), key=lambda kv: kv[1][1].start_byte):
            dnode = self._node_by_id(dnode_id, nnode)
            self._make_symbol(dnode, kind, nnode)

        for cnode, callee, receiver in raw_calls:
            caller = self._enclosing_symbol(cnode)
            self.calls.append(CallInfo(
                caller_id=caller.id if caller else self.file.id,
                callee_name=_text(callee, self.src),
                receiver=(_text(receiver, self.src)[:80] if receiver is not None else None),
                line=cnode.start_point[0] + 1,
                file_id=self.file.id,
            ))

    def _node_by_id(self, node_id: int, hint: Node) -> Node:
        n: Node | None = hint
        while n is not None and n.id != node_id:
            n = n.parent
        assert n is not None
        return n

    def _enclosing_symbol(self, node: Node) -> SymbolInfo | None:
        n = node.parent
        while n is not None:
            if n.id in self.symbol_by_node:
                return self.symbol_by_node[n.id]
            n = n.parent
        return None

    def _scope_chain(self, node: Node) -> list[str]:
        chain: list[str] = []
        n = node.parent
        while n is not None:
            if n.id in self.symbol_by_node:
                chain.insert(0, self.symbol_by_node[n.id].name)
            elif n.type in self.lang.namespace_nodes:
                nm = n.child_by_field_name("name")
                if nm is not None:
                    chain.insert(0, _text(nm, self.src))
            n = n.parent
        return chain

    def _make_symbol(self, dnode: Node, kind: str, nnode: Node) -> None:
        name = _text(nnode, self.src)
        lang = self.lang
        parent = self._enclosing_symbol(dnode)
        kind = lang.adjust_kind(kind, parent)
        chain = lang.scope_chain(dnode, self.src, self._scope_chain(dnode), kind, self.file_namespace)
        qualified = lang.qualified_name(lang.module_prefix(self.file), chain, name)
        sid = ids.symbol(self.repo.tenant, self.repo.name, self.repo.ref, qualified, kind)
        if sid in self.seen_ids:  # overloads / shadowed names inside one file
            sid = f"{sid}~{dnode.start_point[0] + 1}"
        self.seen_ids.add(sid)

        signature = _first_line(dnode, self.src)
        sym = SymbolInfo(
            id=sid,
            file_id=self.file.id,
            name=name,
            qualified_name=qualified,
            kind=kind,
            signature=signature,
            doc=_doc(dnode, self.src, lang),
            visibility=lang.visibility(name, dnode, self.src, signature),
            line_start=dnode.start_point[0] + 1,
            line_end=dnode.end_point[0] + 1,
            content_hash=hashlib.sha1(self.src[dnode.start_byte:dnode.end_byte]).hexdigest(),
            parent_id=parent.id if parent else None,
            is_entry_point=_entry_point(dnode, self.src, signature, lang) if kind in ("function", "method") else False,
        )
        self.symbols.append(sym)
        self.symbol_by_node[dnode.id] = sym


def extract_file(repo: RepoInfo, file: FileInfo) -> tuple[FileExtractor | None, list[str]]:
    cl = load_language(file.language)
    if cl is None:
        return None, [f"{file.path}: no grammar for {file.language} ({GRAMMAR_ERRORS.get(file.language, 'unknown error')})"]
    src = (Path(repo.root) / file.path).read_bytes()
    fx = FileExtractor(repo, file, src, cl)
    try:
        fx.run()
    except Exception as e:  # noqa: BLE001 — one bad file must not abort the run
        return None, [f"{file.path}: extraction failed: {type(e).__name__}: {e}"]
    return fx, []
