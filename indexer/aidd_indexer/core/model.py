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
    layer: str | None = None       # set by conventions (domain | application | adapters-in | ...), else None


@dataclass
class FileInfo:
    id: str
    path: str                      # repo-relative, posix separators
    language: str                  # go | typescript | tsx | javascript | python | csharp | vue | ...
    loc: int
    content_hash: str
    module_id: str
    layer: str | None = None       # set by conventions, else None


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
    receiver_type: str | None = None       # static type of the receiver's base variable as written (`*Complete`, `pw.Policy`,
                                           # or `call:pw.NewPolicy` when it comes from a constructor) — language hook
    receiver_path: tuple[str, ...] = ()    # field chain after the base variable: `uc.policy.Validate` -> ("policy",)


@dataclass
class ImportInfo:
    file_id: str
    spec: str                      # as written: "./util", "github.com/a/b/c", "os", "System.Linq"
    line: int
    bindings: list[str] = field(default_factory=list)  # local names this import introduces (axios, gin, Injectable)


# --- integration candidates (macro, SCHEMA.md §3 / §7) --------------------------------

@dataclass
class HttpEndpointInfo:
    """A route this repo EXPOSES. Macro node (per service); the edges carry ref + evidence."""
    id: str                        # <tenant>/svc/<service>/http/<METHOD> <path-template>
    method: str                    # GET | POST | ... | ANY
    path: str                      # normalized template: /v1/users/{id}
    raw_pattern: str               # as written in the source ("POST /v1/users/{id}")
    framework: str                 # net/http | gin | echo | chi | fiber | gorilla | express | nest | aspnet
    file_id: str
    line: int
    handler_name: str | None       # bare handler name as written (s.createUser -> createUser)
    handler_id: str | None = None  # Symbol id when resolved in the same module
    evidence: str = ""             # repo:path:line


@dataclass
class HttpCallInfo:
    """An outbound HTTP call with a literal (or template) path — a CONSUMES candidate.
    Micro node (per ref); the linker turns it into CONSUMES/CALLED_FROM (F0.5)."""
    id: str                        # <tenant>/<repo>@<ref>/httpcall/<path>:<line>
    method: str                    # GET | POST | ... | ANY
    path: str                      # normalized template
    raw_path: str                  # as written / assembled ("/v1/users/%s")
    via: str                       # PostJSON | http.NewRequest | resty.Get | fetch | axios.post ...
    target_hint: str               # package/dir hint: "tercel" from adapters/outbound/tercel
    env_hints: list[str]           # env var names seen nearby that look like base URLs
    file_id: str
    line: int
    caller_id: str                 # enclosing Symbol id (or File id)
    evidence: str = ""


@dataclass
class ExtractionResult:
    repo: RepoInfo
    modules: list[ModuleInfo] = field(default_factory=list)
    files: list[FileInfo] = field(default_factory=list)
    symbols: list[SymbolInfo] = field(default_factory=list)
    calls: list[CallInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    endpoints: list[HttpEndpointInfo] = field(default_factory=list)
    http_calls: list[HttpCallInfo] = field(default_factory=list)
    violations: list["ViolationInfo"] = field(default_factory=list)   # conventions (F0.4.4)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "modules": len(self.modules),
            "files": len(self.files),
            "symbols": len(self.symbols),
            "calls": len(self.calls),
            "imports": len(self.imports),
            "endpoints": len(self.endpoints),
            "http_calls": len(self.http_calls),
            "violations": len(self.violations),
            "warnings": len(self.warnings),
        }


@dataclass
class ViolationInfo:
    """A convention rule broken at a place in the code (written as a `Violation` node)."""
    id: str
    convention: str                # convention id (e.g. hexagonal)
    rule: str                      # rule id inside the convention (e.g. forbid_import)
    severity: str                  # error | warning | info
    message: str
    file_id: str
    line: int
    symbol_id: str | None
    evidence: str                  # repo:path:line
