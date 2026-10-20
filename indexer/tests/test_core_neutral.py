"""The core is shared by every language, so none of them lives in it: a language registers what is its own (the hooks
of `LanguageSupport`, its `PackageFacts`) from `languages/<lang>/`, and the core reaches it only through the registry."""

import ast
from pathlib import Path

from aidd_indexer import languages

PACKAGE = Path(__file__).resolve().parents[1] / "aidd_indexer"
CORE = PACKAGE / "core"
LANGUAGE_PACKAGES = {p.name for p in (PACKAGE / "languages").iterdir() if (p / "__init__.py").exists()}


def _modules():
    for f in sorted(CORE.rglob("*.py")):
        yield f.relative_to(PACKAGE).as_posix(), ast.parse(f.read_text())


def _imported(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    if isinstance(node, ast.ImportFrom):
        return [f"{node.module or ''}.{a.name}" for a in node.names]
    return []


def _language_of(name: str) -> str | None:
    """`languages.go.http` → `go`; `languages.base` and the registry itself → None."""
    parts = name.split(".")
    after = parts[parts.index("languages") + 1:] if "languages" in parts else []
    return after[0] if after and after[0] in LANGUAGE_PACKAGES else None


def test_no_core_module_imports_a_language():
    found = [f"{rel}: {name}" for rel, tree in _modules() for node in ast.walk(tree) for name in _imported(node)
             if _language_of(name)]
    assert found == []


def test_no_core_code_names_a_language():
    ids = {lang.id for lang in languages.all()} | LANGUAGE_PACKAGES
    found = [f"{rel}:{node.lineno}: {node.value!r}" for rel, tree in _modules() for node in ast.walk(tree)
             if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.lower() in ids]
    assert found == []
