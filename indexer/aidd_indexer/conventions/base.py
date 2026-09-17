"""The extension contract for *conventions* — the rules of a development pattern (ADR-003 §conventions).

A convention is anything the generic indexer cannot know about a codebase: which directories are
which architectural layer, which layers may depend on which, where HTTP entry points are allowed
to live, which outbound-client folder talks to which service. Conventions run **after** extraction
and resolution and may (a) annotate the result — `File.layer`, `Module.layer`, refined
`HttpCall.target_hint`, `Symbol.is_entry_point` — and (b) emit `Violation`s.

Every hook has a no-op default; a convention overrides what it needs. Conventions are plugged in
three ways (see `conventions/__init__.py`): a `convention.yaml` file (declarative,
`conventions/declarative.py`), a Python class published under the `aidd.conventions` entry-point
group, or a dotted `module:Class` path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.model import ExtractionResult, FileInfo, HttpCallInfo, ModuleInfo, SymbolInfo, ViolationInfo
from ..core.resolve import Resolved


@dataclass
class ConventionContext:
    """What `check` sees: the extraction, the resolved edges and the layer of every file/module."""
    res: ExtractionResult
    rv: Resolved
    file_layer: dict[str, str] = field(default_factory=dict)      # file id -> layer
    module_layer: dict[str, str] = field(default_factory=dict)    # module id -> layer
    files_by_id: dict[str, FileInfo] = field(default_factory=dict)

    def layer_of_file(self, file_id: str) -> str | None:
        return self.file_layer.get(file_id)


class Convention:
    """Base class. `id` names the convention in `Violation.convention` and in atlas.yaml."""

    id: str = ""

    def configure(self, options: dict[str, Any]) -> None:
        """Options from atlas.yaml (`conventions: [{id: x, options: {...}}]`)."""
        return None

    # ---- annotation hooks (called per element, first non-None answer wins across conventions)
    def layer_of(self, file: FileInfo, module: ModuleInfo | None) -> str | None:
        return None

    def target_of(self, call: HttpCallInfo, file: FileInfo) -> str | None:
        """A better `target_hint` (service name) for an outbound call, or None to keep the heuristic."""
        return None

    def is_entry_point(self, symbol: SymbolInfo, file: FileInfo) -> bool | None:
        """Override the language heuristic: True/False, or None to keep it."""
        return None

    # ---- rules
    def check(self, ctx: ConventionContext) -> list[ViolationInfo]:
        return []
