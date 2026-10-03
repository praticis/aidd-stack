"""Go language support: packages as modules, receiver-scoped methods, go.mod based import resolution,
and static receiver types for method calls (`uc.policy.Validate()` → `password.Policy.Validate`)."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from tree_sitter import Node

from ...core import ids
from ...core.model import FileInfo, ModuleInfo, RepoInfo, SymbolInfo
from ..base import LanguageSupport, PackageFactory, ResolveContext, node_text, walk
from .http import GoScanner

HERE = Path(__file__).parent


def _go_module_path(root: Path, module: ModuleInfo) -> str | None:
    gm = root / module.path / "go.mod" if module.path else root / "go.mod"
    if not gm.exists():
        return None
    for line in gm.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("module "):
            return line.split(None, 1)[1].strip()
    return None


_FUNC_NODES = ("function_declaration", "method_declaration", "func_literal")
_TYPE_NODES = ("type_identifier", "qualified_type", "pointer_type", "generic_type")


def _type_text(node: Node | None, src: bytes) -> str | None:
    """`*pkg.T`, `[]T`, `pkg.T` → `pkg.T` / `T`; None for func/map/chan/interface literals."""
    n = node
    while n is not None and n.type in ("pointer_type", "slice_type", "array_type", "parenthesized_type"):
        n = next((c for c in n.children if c.is_named), None)
    if n is None or n.type not in ("type_identifier", "qualified_type", "generic_type"):
        return None
    if n.type == "generic_type":
        n = next((c for c in n.children if c.type in ("type_identifier", "qualified_type")), None)
        if n is None:
            return None
    return node_text(n, src)


def _declared_type(name: str, scope: Node, src: bytes, before: int) -> str | None:
    """Type of local variable `name` inside `scope` (a function): receiver, parameter, `var x T`,
    `x := T{}` / `&T{}`, or `x := pkg.New(...)` (reported as `call:pkg.New` for the resolver)."""
    for pl in [c for c in scope.children if c.type == "parameter_list"]:      # receiver + params
        for pd in pl.children:
            if pd.type != "parameter_declaration":
                continue
            names = [c for c in pd.children if c.type == "identifier"]
            typ = next((c for c in pd.children if c.type in _TYPE_NODES or c.type.endswith("_type")), None)
            if any(node_text(nm, src) == name for nm in names):
                return _type_text(typ, src)
    best: str | None = None
    for d in walk(scope):
        if d.start_byte >= before:
            break
        if d.type == "short_var_declaration":
            left, right = d.child_by_field_name("left"), d.child_by_field_name("right")
            if left is None or right is None:
                continue
            lefts = [c for c in left.children if c.is_named]
            rights = [c for c in right.children if c.is_named]
            for i, l in enumerate(lefts):
                if node_text(l, src) != name:
                    continue
                if i >= len(rights):
                    if len(rights) == 1 and rights[0].type == "call_expression":
                        r = rights[0]                                     # multi-value call
                    else:
                        continue
                else:
                    r = rights[i]
                if r.type == "unary_expression":                                  # &T{...}
                    r = next((c for c in r.children if c.is_named), r)
                if r.type == "composite_literal":
                    best = _type_text(r.child_by_field_name("type"), src)
                elif r.type == "call_expression":
                    fn = r.child_by_field_name("function")
                    if fn is not None and fn.type in ("identifier", "selector_expression"):
                        # `uc, repo := setup(t)`: one call, several results → remember which one
                        best = "call:" + node_text(fn, src) + (f"#{i}" if len(lefts) > 1 and len(rights) == 1 else "")
                else:
                    best = None
        elif d.type == "var_spec":
            names = [c for c in d.children if c.type == "identifier"]
            typ = d.child_by_field_name("type")
            if any(node_text(nm, src) == name for nm in names) and typ is not None:
                best = _type_text(typ, src)
    return best


def _receiver(node: Node, src: bytes) -> str | None:
    recv = node.child_by_field_name("receiver")
    if recv is None:
        return None
    for tid in walk(recv):
        if tid.type == "type_identifier":
            return node_text(tid, src)
    return None


_GO_MODULE_LINE = re.compile(r"^module\s+(\S+)", re.M)
_GO_REQUIRE_LINE = re.compile(r"^\s*(?:require\s+)?([a-zA-Z0-9.\-_~/]+\.[a-zA-Z0-9.\-_~/]+)\s+(v[^\s/]+)(?:\s*//.*)?$", re.M)


class GoSupport(LanguageSupport):
    # ---- discovery: every directory with .go files is a package — the unit imports point at
    def discover_modules(self, repo: RepoInfo, rel_files: list[str], modules: dict[str, ModuleInfo]) -> None:
        for r in rel_files:
            p = PurePosixPath(r)
            if p.suffix == ".go" and not p.name.endswith("_test.go"):
                d = str(p.parent) if str(p.parent) != "." else ""
                if d not in modules:
                    modules[d] = ModuleInfo(
                        id=ids.module(repo.tenant, repo.name, repo.ref, d),
                        name=(p.parent.name if d else repo.name),
                        path=d,
                        kind="go-package",
                    )

    # ---- symbols
    def module_prefix(self, file: FileInfo) -> str:
        d = str(PurePosixPath(file.path).parent)
        return "" if d == "." else d.replace("/", ".")

    def qualified_name(self, prefix: str, chain: list[str], name: str) -> str:
        return ".".join(([prefix] if prefix else []) + chain + [name])

    def scope_chain(self, dnode: Node, src: bytes, chain: list[str], kind: str, file_namespace: str | None) -> list[str]:
        if kind == "method":
            recv = _receiver(dnode, src)
            if recv:
                return [recv]
        return chain

    def visibility(self, name: str, node: Node, src: bytes, first_line: str) -> str:
        return "public" if name[:1].isupper() else "private"

    def import_bindings(self, stmt_text: str, stmt: Node, spec: str, src: bytes) -> list[str]:
        alias = stmt.child_by_field_name("name")
        if alias is not None:
            return [node_text(alias, src)]
        base = spec.rstrip("/").split("/")[-1]
        base = re.sub(r"^v\d+$", "", base) or spec.rstrip("/").split("/")[-2]
        return [re.sub(r"[-.].*$", "", base) or base]

    # ---- static receiver types (F0.7.1)
    def file_facts(self, root: Node, src: bytes) -> dict[str, Any]:
        structs: dict[str, dict[str, str]] = {}
        embeds: dict[str, list[str]] = {}
        funcs: dict[str, list[str]] = {}
        imports: dict[str, str] = {}
        for n in walk(root):
            if n.type == "type_spec":
                name, typ = n.child_by_field_name("name"), n.child_by_field_name("type")
                if name is not None and typ is not None and typ.type == "struct_type":
                    fields: dict[str, str] = {}
                    embedded: list[str] = []
                    for fd in walk(typ):
                        if fd.type != "field_declaration":
                            continue
                        ftype = next((c for c in fd.children if c.type in _TYPE_NODES or c.type.endswith("_type")), None)
                        tt = _type_text(ftype, src)
                        if tt is None:
                            continue
                        names = [node_text(c, src) for c in fd.children if c.type == "field_identifier"]
                        if not names:                                            # embedded: `Config` / `*Config` — fields are promoted
                            embedded.append(tt)
                            names = [tt.split(".")[-1]]
                        for fname in names:
                            fields[fname] = tt
                    structs[node_text(name, src)] = fields
                    if embedded:
                        embeds[node_text(name, src)] = embedded
            elif n.type == "function_declaration":
                name, result = n.child_by_field_name("name"), n.child_by_field_name("result")
                if name is not None and result is not None:
                    if result.type == "parameter_list":                       # (*T, error) / (a, b T)
                        rets: list[str] = []
                        for pd in result.children:
                            if pd.type != "parameter_declaration":
                                continue
                            ty = next((c for c in pd.children if c.type in _TYPE_NODES or c.type.endswith("_type")), None)
                            n_names = max(1, sum(1 for c in pd.children if c.type == "identifier"))
                            rets += [_type_text(ty, src) or ""] * n_names
                        funcs[node_text(name, src)] = rets
                    else:
                        tt = _type_text(result, src)
                        if tt:
                            funcs[node_text(name, src)] = [tt]
            elif n.type == "import_spec":
                path = n.child_by_field_name("path")
                if path is not None:
                    spec = node_text(path, src).strip('"`')
                    for alias in self.import_bindings("", n, spec, src):
                        imports[alias] = spec
        return {"structs": structs, "embeds": embeds, "funcs": funcs, "imports": imports}

    def call_receiver(self, call: Node, receiver: Node, src: bytes) -> tuple[str, tuple[str, ...]] | None:
        # receiver = `uc.policy` (selector chain) or `p` (identifier); anything else (call results,
        # index expressions) is not followed.
        chain: list[str] = []
        n = receiver
        while n.type == "selector_expression":
            fld = n.child_by_field_name("field")
            if fld is None:
                return None
            chain.insert(0, node_text(fld, src))
            n = n.child_by_field_name("operand")
            if n is None:
                return None
        if n.type != "identifier":
            return None
        base = node_text(n, src)
        scope = call.parent
        while scope is not None and scope.type not in _FUNC_NODES:
            scope = scope.parent
        if scope is None:
            return None
        typ = _declared_type(base, scope, src, call.start_byte)
        if typ is None and scope.type == "func_literal":                      # closure: look at the enclosing function
            outer = scope.parent
            while outer is not None and outer.type not in _FUNC_NODES:
                outer = outer.parent
            if outer is not None:
                typ = _declared_type(base, outer, src, call.start_byte)
        return (typ, tuple(chain)) if typ else None

    def _package_prefix(self, ctx: ResolveContext, file: FileInfo, alias: str | None) -> str | None:
        """Qualified-name prefix (dotted directory) of a type reference: the file's own package when
        unqualified, else the package the alias imports (only modules of this repo resolve)."""
        if alias is None:
            d = str(PurePosixPath(file.path).parent)
            return "" if d == "." else d.replace("/", ".")
        spec = (ctx.facts.get(file.id) or {}).get("imports", {}).get(alias)
        if not spec:
            return None
        for mp, m in ctx.extra.get("go_modules", ()):
            if spec == mp or spec.startswith(mp + "/"):
                rel = spec[len(mp):].strip("/")
                pkg_dir = "/".join(p for p in (m.path, rel) if p)
                return pkg_dir.replace("/", ".")
        return None

    def _files_in(self, ctx: ResolveContext, prefix: str) -> list[FileInfo]:
        """Go files of the package whose dotted directory is `prefix` ("" = repo root)."""
        d = prefix.replace(".", "/") or "."
        return [f for f in ctx.files_by_path.values()
                if f.language == self.id and str(PurePosixPath(f.path).parent) == d]

    def _resolve_type(self, ctx: ResolveContext, file: FileInfo, text: str) -> tuple[str, str] | None:
        """`pw.Policy` as written in `file` → (package prefix, TypeName)."""
        if text.startswith("call:"):
            fn, _, idx = text[5:].partition("#")
            alias, _, fname = fn.rpartition(".")
            prefix = self._package_prefix(ctx, file, alias or None)
            if prefix is None:
                return None
            for f in self._files_in(ctx, prefix):
                rets = (ctx.facts.get(f.id) or {}).get("funcs", {}).get(fname)
                if rets:
                    i = int(idx) if idx else 0
                    return self._resolve_type(ctx, f, rets[i]) if i < len(rets) and rets[i] else None
            return None
        alias, _, name = text.rpartition(".")
        prefix = self._package_prefix(ctx, file, alias or None)
        return (prefix, name) if prefix is not None else None

    def _field_type(self, ctx: ResolveContext, owner: tuple[str, str], field: str, depth: int) -> tuple[str, str] | None:
        """Type of `owner.field`, looking through embedded structs (promoted fields) up to 4 levels."""
        if depth > 4:
            return None
        prefix, tname = owner
        for f in self._files_in(ctx, prefix):
            facts = ctx.facts.get(f.id) or {}
            st = facts.get("structs", {}).get(tname)
            if st is None:
                continue
            if field in st:
                return self._resolve_type(ctx, f, st[field])
            for emb in facts.get("embeds", {}).get(tname, []):
                inner = self._resolve_type(ctx, f, emb)
                hit = self._field_type(ctx, inner, field, depth + 1) if inner else None
                if hit:
                    return hit
            return None
        return None

    def resolve_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str, path: tuple[str, ...]) -> str | None:
        cur = self._resolve_type(ctx, file, receiver_type)
        for field in path:
            if cur is None:
                return None
            cur = self._field_type(ctx, cur, field, depth=0)
        if cur is None:
            return None
        prefix, tname = cur
        return f"{prefix}.{tname}" if prefix else tname

    # ---- resolution
    def manifest_deps(self, rel_path: str, text: str) -> tuple[list[str], list[tuple[str, str]]]:
        """go.mod: `module` publishes; `require` lines (single or block) are direct deps unless
        marked `// indirect`."""
        names = _GO_MODULE_LINE.findall(text)
        deps = [(m.group(1), m.group(2)) for m in _GO_REQUIRE_LINE.finditer(text) if "// indirect" not in m.group(0)]
        return names, deps

    def resolve_setup(self, ctx: ResolveContext) -> None:
        # module paths from go.mod, longest first
        ctx.extra["go_modules"] = sorted(
            ((mp, m) for m in ctx.modules_by_path.values()
             if m.kind == "go-module" and (mp := _go_module_path(ctx.root, m))),
            key=lambda t: -len(t[0]),
        )

    def resolve_import(self, ctx: ResolveContext, file: FileInfo, spec: str, pkg: PackageFactory) -> tuple[str, str] | None:
        for mp, m in ctx.extra.get("go_modules", ()):
            if spec == mp or spec.startswith(mp + "/"):
                rel = spec[len(mp):].strip("/")
                pkg_dir = "/".join(p for p in (m.path, rel) if p)
                mod = ctx.modules_by_path.get(pkg_dir)
                return (mod.id, "Module") if mod else None
        first = spec.split("/")[0]
        stdlib = "." not in first
        name = spec if stdlib else "/".join(spec.split("/")[:3])
        return (pkg("go", name, stdlib), "Package")

    def link_symbols(self, symbols: list[SymbolInfo], files_by_id: dict[str, FileInfo]) -> None:
        """Methods → receiver struct as parent (`pkg.Type.Method` → `pkg.Type`)."""
        by_q = {s.qualified_name: s for s in symbols if s.kind in ("struct", "type", "interface")}
        for s in symbols:
            if s.kind == "method" and s.parent_id is None and files_by_id[s.file_id].language == self.id:
                owner = s.qualified_name.rsplit(".", 1)[0]
                if owner in by_q:
                    s.parent_id = by_q[owner].id


LANGUAGES = [
    GoSupport(
        id="go", grammar="go", extensions=(".go",), query_file=HERE / "queries.scm", stack="go",
        manifests={"go.mod": "go-module"}, ecosystem="go", http_scanner=GoScanner,
        entry_point_hints=("http.ResponseWriter", "*gin.Context", "echo.Context", "*fiber.Ctx", "context.Context, req"),
    ),
]
