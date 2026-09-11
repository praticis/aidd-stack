"""In-memory model produced by extraction, consumed by the graph writer.

Mirrors neo4j/SCHEMA.md (v1). Ids follow §4 of that document and are
built exclusively through `ids.py`, never by hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RepoInfo:
    tenant: str
    name: str
    ref: str
    commit_sha: str
    root: str                      # absolute path on disk
    stack: list[str] = field(default_factory=list)
    default_ref: str = "main"
    url: str = ""


@dataclass
class ModuleInfo:
    id: str
    name: str
    path: str                      # repo-relative directory ("" = repo root)
    kind: str                      # go-module | npm-package | csproj | py-package | root


@dataclass
class FileInfo:
    id: str
    path: str                      # repo-relative, posix separators
    language: str                  # go | typescript | tsx | javascript | python | csharp | vue | ...
    loc: int
    content_hash: str
    module_id: str


@dataclass
class SymbolInfo:
    id: str
    file_id: str
    name: str
    qualified_name: str
    kind: str                      # class | interface | struct | enum | function | method | type | const
    signature: str
    doc: str
    visibility: str                # public | private | unknown
    line_start: int
    line_end: int
    content_hash: str
    parent_id: str | None = None   # enclosing symbol (member CONTAINS)
    is_entry_point: bool = False


@dataclass
class CallInfo:
    caller_id: str                 # symbol id (or file id when the call is at top level)
    callee_name: str               # bare name as written (last segment)
    receiver: str | None           # `x` in x.Foo(), None for bare calls
    line: int
    file_id: str


@dataclass
class ImportInfo:
    file_id: str
    spec: str                      # as written: "./util", "github.com/a/b/c", "os", "System.Linq"
    line: int
    bindings: list[str] = field(default_factory=list)  # local names this import introduces (axios, gin, Injectable)


@dataclass
class ExtractionResult:
    repo: RepoInfo
    modules: list[ModuleInfo] = field(default_factory=list)
    files: list[FileInfo] = field(default_factory=list)
    symbols: list[SymbolInfo] = field(default_factory=list)
    calls: list[CallInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "modules": len(self.modules),
            "files": len(self.files),
            "symbols": len(self.symbols),
            "calls": len(self.calls),
            "imports": len(self.imports),
            "warnings": len(self.warnings),
        }
