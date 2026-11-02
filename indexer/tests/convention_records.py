"""Hand-made records for the conventions' tests: a repo's modules, files, symbols, routes and outbound calls, and the
resolved imports a convention reads, with no extraction."""
from __future__ import annotations

from aidd_indexer.conventions.base import ConventionContext
from aidd_indexer.core.edges import ImportEdge
from aidd_indexer.core.model import (ExtractionResult, FileInfo, HttpCallInfo, HttpEndpointInfo, ModuleInfo, RepoInfo,
                                     SymbolInfo)
from aidd_indexer.core.resolve import Resolved


def module(id: str) -> ModuleInfo:
    return ModuleInfo(id=id, name=id, path=id, kind="csproj")


def file(path: str, module_id: str = "m") -> FileInfo:
    return FileInfo(id=path, path=path, language="csharp", loc=1, content_hash="", module_id=module_id)


def symbol(name: str, file_id: str, line: int = 1, signature: str = "", kind: str = "class",
           parent_id: str | None = None, is_entry_point: bool = False) -> SymbolInfo:
    return SymbolInfo(id=f"{file_id}#{name}", file_id=file_id, name=name, qualified_name=name, kind=kind,
                      signature=signature, doc="", visibility="public", line_start=line, line_end=line,
                      content_hash="", parent_id=parent_id, is_entry_point=is_entry_point)


def endpoint(method: str, path: str, file_id: str, line: int, handler_id: str | None = None) -> HttpEndpointInfo:
    return HttpEndpointInfo(id=f"{method} {path}", method=method, path=path, raw_pattern=path, framework="aspnet",
                            file_id=file_id, line=line, handler_name=None, handler_id=handler_id)


def http_call(method: str, path: str, file_id: str, line: int = 1, caller_id: str = "",
              target_hint: str = "") -> HttpCallInfo:
    return HttpCallInfo(id=f"{file_id}:{line}", method=method, path=path, raw_path=path, via="PostAsync",
                        target_hint=target_hint, env_hints=[], file_id=file_id, line=line, caller_id=caller_id)


def import_edge(file_id: str, target_label: str, target_id: str, line: int, spec: str = "") -> ImportEdge:
    return ImportEdge(file_id=file_id, target_id=target_id, target_label=target_label, line=line, spec=spec)


def result(root: str = "/repo", modules=(), files=(), symbols=(), endpoints=(), http_calls=()) -> ExtractionResult:
    return ExtractionResult(repo=RepoInfo(tenant="t", name="shop", ref="main", commit_sha="x", root=root),
                            modules=list(modules), files=list(files), symbols=list(symbols),
                            endpoints=list(endpoints), http_calls=list(http_calls))


def resolved(imports=(), namespace_files: dict[str, list[str]] | None = None) -> Resolved:
    return Resolved(calls=[], imports=list(imports), packages={}, unresolved_calls=0, unresolved_imports=0,
                    namespace_files=namespace_files or {})


def context(res: ExtractionResult, rv: Resolved | None = None) -> ConventionContext:
    return ConventionContext(res=res, rv=rv or resolved(), files_by_id={f.id: f for f in res.files})
