"""tree-sitter extraction: symbols, call sites and imports per file.

Language queries live in `queries/<language>.scm`. Each blank-line-separated
pattern is compiled on its own so a pattern the installed grammar does not
support is skipped (with a warning) instead of disabling the language.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path, PurePosixPath

from tree_sitter import Language, Node, Parser, Query, QueryCursor, QueryError
from tree_sitter_language_pack import get_language, get_parser

from . import ids
from .model import CallInfo, FileInfo, ImportInfo, RepoInfo, SymbolInfo

QUERY_DIR = Path(__file__).parent / "queries"

# Symbol kinds that a call can target.
CALLABLE_KINDS = {"function", "method", "class", "struct"}

# Scope-bearing nodes that are not symbols but prefix qualified names.
NAMESPACE_NODES = {"namespace_declaration", "file_scoped_namespace_declaration"}

ENTRY_POINT_HINTS = (
    # Go
    "http.ResponseWriter", "*gin.Context", "echo.Context", "*fiber.Ctx", "context.Context, req",
    # TS (NestJS/Express) — decorators are matched on preceding siblings, see _entry_point
    # C#
    "[HttpGet", "[HttpPost", "[HttpPut", "[HttpDelete", "[HttpPatch", "[Route", "IActionResult",
)
DECORATOR_ENTRY = re.compile(r"@(Get|Post|Put|Delete|Patch|All|MessagePattern|EventPattern|Cron|Query|Mutation|GrpcMethod|SqsMessageHandler|RabbitSubscribe|Process)\b"
                             r"|@(app|router|api|bp|blueprint)\.(get|post|put|delete|patch|route|websocket)\b"
                             r"|\[(HttpGet|HttpPost|HttpPut|HttpDelete|HttpPatch|Route|Function|ServiceBusTrigger|QueueTrigger)\b")


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
    grammar = "csharp" if name == "csharp" else name
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
    src_file = QUERY_DIR / f"{name}.scm"
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


def _text(node: Node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


_ATTR_PREFIX = re.compile(r"^(\s*(\[[^\]]*\]|@[\w.]+(\([^)]*\))?)\s*)+")


def _first_line(node: Node, src: bytes, limit: int = 200) -> str:
    t = _ATTR_PREFIX.sub("", _text(node, src))
    for stop in ("{", "\n"):
        i = t.find(stop)
        if i > 0:
            t = t[:i]
    t = t.rstrip(" :=>")
    return " ".join(t.split())[:limit]


def _doc(node: Node, src: bytes, language: str) -> str:
    parts: list[str] = []
    sib = node.prev_sibling
    while sib is not None and sib.type in ("comment", "line_comment", "block_comment", "decorator", "attribute_list"):
        if sib.type in ("comment", "line_comment", "block_comment"):
            parts.insert(0, _text(sib, src))
        sib = sib.prev_sibling
    if language == "python":
        body = node.child_by_field_name("body")
        if body is not None and body.child_count and body.children[0].type == "expression_statement":
            first = body.children[0].children[0] if body.children[0].child_count else None
            if first is not None and first.type == "string":
                parts.append(_text(first, src))
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


def _entry_point(node: Node, src: bytes, signature: str) -> bool:
    if any(h in signature for h in ENTRY_POINT_HINTS):
        return True
    return bool(DECORATOR_ENTRY.search(_leading_decorators(node, src)))


def _visibility(name: str, node: Node, src: bytes, language: str) -> str:
    if language == "go":
        return "public" if name[:1].isupper() else "private"
    if language == "python":
        return "private" if name.startswith("_") else "public"
    head = _first_line(node, src)
    if re.search(r"\b(private|protected|internal)\b", head):
        return "private"
    if re.search(r"\b(public|export)\b", head):
        return "public"
    if node.parent is not None and node.parent.type == "export_statement":
        return "public"
    return "unknown"


def _go_receiver(node: Node, src: bytes) -> str | None:
    recv = node.child_by_field_name("receiver")
    if recv is None:
        return None
    for tid in _walk(recv):
        if tid.type == "type_identifier":
            return _text(tid, src)
    return None


def _ancestors(node: Node):
    n = node.parent
    while n is not None:
        yield n
        n = n.parent


_TS_IMPORT = re.compile(r"import\s+(?:type\s+)?(?:(\w+)\s*,?\s*)?(?:\*\s+as\s+(\w+))?\s*(?:\{([^}]*)\})?")
_PY_IMPORT = re.compile(r"^\s*(?:from\s+[\w.]+\s+)?import\s+(.*)$", re.S)


def _import_bindings(inode: Node, spec: str, src: bytes, language: str) -> list[str]:
    """Local names introduced by the import statement that contains `inode`."""
    stmt = inode
    while stmt is not None and stmt.type not in ("import_statement", "import_spec", "import_from_statement",
                                                 "using_directive", "lexical_declaration", "expression_statement"):
        stmt = stmt.parent
    if stmt is None:
        return []
    text = _text(stmt, src)
    if language in ("typescript", "tsx", "javascript"):
        m = _TS_IMPORT.search(text)
        names: list[str] = []
        if m:
            if m.group(1): names.append(m.group(1))
            if m.group(2): names.append(m.group(2))
            if m.group(3):
                for part in m.group(3).split(","):
                    part = part.strip()
                    if part:
                        names.append(part.split(" as ")[-1].strip())
        rq = re.search(r"(?:const|let|var)\s+(\w+)\s*=\s*require", text)
        if rq: names.append(rq.group(1))
        return names
    if language == "go":
        alias = stmt.child_by_field_name("name")
        if alias is not None:
            return [_text(alias, src)]
        base = spec.rstrip("/").split("/")[-1]
        base = re.sub(r"^v\d+$", "", base) or spec.rstrip("/").split("/")[-2]
        return [re.sub(r"[-.].*$", "", base) or base]
    if language == "python":
        m = _PY_IMPORT.match(text)
        if not m:
            return []
        names = []
        for part in m.group(1).replace("(", "").replace(")", "").split(","):
            part = part.strip()
            if not part: continue
            if " as " in part: names.append(part.split(" as ")[-1].strip())
            else: names.append(part.split(".")[0])
        return names
    return []


def _walk(node: Node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def _module_of(file: FileInfo) -> str:
    """Scope prefix for qualified names: directory (Go) or path without ext."""
    p = PurePosixPath(file.path)
    if file.language == "go":
        d = str(p.parent)
        return "" if d == "." else d.replace("/", ".")
    return str(p.with_suffix("")) if file.language != "csharp" else ""


class FileExtractor:
    def __init__(self, repo: RepoInfo, file: FileInfo, src: bytes, cl: CompiledLanguage):
        self.repo, self.file, self.src, self.cl = repo, file, src, cl
        self.tree = cl.parser.parse(src)
        self.defs: dict[int, tuple[str, Node]] = {}   # def node id -> (kind, name node)
        self.symbol_by_node: dict[int, SymbolInfo] = {}
        self.symbols: list[SymbolInfo] = []
        self.calls: list[CallInfo] = []
        self.imports: list[ImportInfo] = []
        self.namespaces: list[str] = []                # C# namespaces declared in this file
        self.file_namespace: str | None = None         # C# `namespace X;` (file-scoped) — prefixes everything
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
                        bindings=_import_bindings(inode, spec, self.src, self.file.language),
                    ))
        if self.file.language == "csharp":
            for n in _walk(self.tree.root_node):
                if n.type in NAMESPACE_NODES:
                    nm = n.child_by_field_name("name")
                    if nm is not None:
                        self.namespaces.append(_text(nm, self.src))
                        if n.type == "file_scoped_namespace_declaration":
                            self.file_namespace = _text(nm, self.src)

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
            elif n.type in NAMESPACE_NODES:
                nm = n.child_by_field_name("name")
                if nm is not None:
                    chain.insert(0, _text(nm, self.src))
            n = n.parent
        return chain

    def _make_symbol(self, dnode: Node, kind: str, nnode: Node) -> None:
        name = _text(nnode, self.src)
        lang = self.file.language
        parent = self._enclosing_symbol(dnode)
        chain = self._scope_chain(dnode)

        if lang == "python" and kind == "function" and parent is not None and parent.kind == "class":
            kind = "method"
        if lang == "go" and kind == "method":
            recv = _go_receiver(dnode, self.src)
            if recv:
                chain = [recv]

        prefix = _module_of(self.file)
        if lang == "csharp" and self.file_namespace and not any(
            n.type in NAMESPACE_NODES for n in _ancestors(dnode)
        ):
            chain = [self.file_namespace] + chain
        parts = ([prefix] if prefix else []) + chain + [name]
        qualified = ".".join(parts) if lang in ("go", "csharp") else (
            (prefix + ":" if prefix else "") + ".".join(chain + [name])
        )
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
            visibility=_visibility(name, dnode, self.src, lang),
            line_start=dnode.start_point[0] + 1,
            line_end=dnode.end_point[0] + 1,
            content_hash=hashlib.sha1(self.src[dnode.start_byte:dnode.end_byte]).hexdigest(),
            parent_id=parent.id if parent else None,
            is_entry_point=_entry_point(dnode, self.src, signature) if kind in ("function", "method") else False,
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
