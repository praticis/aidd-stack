"""Routes a file's place declares.

- Next.js, in a package that depends on `next`: `app/**/route.ts` exporting `GET`, `POST`.. (App Router) and
  `pages/api/**` with a default export that answers any verb (Pages Router). A folder `[id]` is a parameter, `[...rest]`
  one too and `[[...rest]]` also the folder's own path; `(group)` and `@slot` add nothing; nothing under a `_private`
  folder is a route.
- `@fastify/autoload`: `app.register(autoload, { dir: path.join(__dirname, "routes") })` registers every file under
  the directory as a plugin, under its folders' path (`routes/api/tasks/index.ts` → `/api/tasks`) and the `prefix` of
  its `options`: the router each file's default export receives is mounted where `app` is."""

from __future__ import annotations

import posixpath
import re

from tree_sitter import Node

from ...core.http_base import HttpResult, text, unwrap_arg
from ...core.paths import HTTP_METHODS, unquote

SOURCE = r"\.[cm]?[jt]sx?$"
APP_ROUTE = re.compile(r"^(?:src/)?app/(?P<dir>(?:.+/)?)route" + SOURCE)
PAGES_API = re.compile(r"^(?:src/)?pages/(?P<path>api(?:/.+)?)" + SOURCE)
AUTOLOAD = "ts.autoload"            # fact: directory → (where its plugins are mounted, prefix, folder prefixes)
AUTOLOAD_SPECS = ("@fastify/autoload", "fastify-autoload")
HERE = ("__dirname", "import.meta.dirname")


class TsFileRoutes:
    """Mixin of the TS scanner."""

    def file_routes(self) -> None:
        """This file's routes by Next.js' layout, when its package uses Next.js."""
        view = self.ctx.view
        root = view.manifest_dir(self.fx.file, "next") if view is not None else None
        if root is None:
            return
        rel = self.fx.file.path[len(root) + 1:] if root else self.fx.file.path
        app, pages = APP_ROUTE.match(rel), PAGES_API.match(rel)
        if app is not None:
            paths = _route_paths(app.group("dir"))
            for method, node, handler in self._exported_verbs():
                for p in paths:
                    self.add_endpoint(node, method, p, "next", handler)
        elif pages is not None:
            path = re.sub(r"/index$", "", pages.group("path"))
            node, handler = self._default_export()
            for p in _route_paths(path) if node is not None else ():
                self.add_endpoint(node, "ANY", p, "next", handler)

    def _exported_verbs(self) -> list[tuple[str, Node, Node]]:
        """(verb, where, handler name) of each export named like a verb: `export async function GET`, `export const
        PATCH = ..`, `export { remove as DELETE }`."""
        out = []
        for st in (c for c in self.fx.tree.root_node.named_children if c.type == "export_statement"):
            decl = st.child_by_field_name("declaration")
            names = [decl.child_by_field_name("name")] if decl is not None and decl.type == "function_declaration" else \
                [d.child_by_field_name("name") for d in decl.named_children if d.type == "variable_declarator"] \
                if decl is not None and decl.type == "lexical_declaration" else []
            out += [(text(nm, self.src), nm, nm) for nm in names if nm is not None and text(nm, self.src) in HTTP_METHODS]
            for s in (s for c in st.named_children if c.type == "export_clause" for s in c.named_children):
                name, alias = s.child_by_field_name("name"), s.child_by_field_name("alias")
                verb = text(alias if alias is not None else name, self.src) if name is not None else ""
                if verb in HTTP_METHODS:
                    out.append((verb, s, name))
        return out

    def _default_export(self) -> tuple[Node | None, Node | None]:
        """Where the module's default export is, and its function's name when it names one."""
        for st in self.fx.tree.root_node.named_children:
            if st.type == "export_statement" and any(c.type == "default" for c in st.children):
                value = st.child_by_field_name("declaration") or st.child_by_field_name("value")
                name = value.child_by_field_name("name") if value is not None and value.type in (
                    "function_declaration", "function_expression", "function") else None
                return st, name if name is not None else value if value is not None and value.type == "identifier" else None
        return None, None

    # -- @fastify/autoload --------------------------------------------------------------------------------------
    def autoload(self, n: Node, name: str, recv_last: str, arg_nodes: list[Node]) -> bool:
        """`app.register(autoload, { dir, options: { prefix } })`: kept for `finish`, which knows where `app` leads."""
        plugin = unwrap_arg(arg_nodes[0]) if name == "register" and len(arg_nodes) > 1 else None
        spec = (self.imports.get(text(plugin, self.src)) or (None,))[0] if plugin is not None else None
        opts = unwrap_arg(arg_nodes[1]) if spec in AUTOLOAD_SPECS else None
        fields = dict(self._own_fields(opts)) if opts is not None and opts.type == "object" else {}
        d = self._dir_of(fields.get("dir"))
        if d is None:
            return False
        inner = fields.get("options")
        given = dict(self._own_fields(inner)).get("prefix") if inner is not None and inner.type == "object" else None
        prefix = (self.path_of(given) or "") if given is not None else ""
        folders = text(fields["dirNameRoutePrefix"], self.src) != "false" if "dirNameRoutePrefix" in fields else True
        self.__dict__.setdefault("autoloads", []).append((d, self.router_key(recv_last, n), prefix, folders))
        return True

    def _dir_of(self, v: Node | None) -> str | None:
        """The repo directory `path.join(__dirname, "routes")` names (also `import.meta.dirname`, `resolve`)."""
        f = v.child_by_field_name("function") if v is not None and v.type == "call_expression" else None
        args = [unwrap_arg(a) for a in v.child_by_field_name("arguments").named_children] if f is not None else []
        if not args or text(f, self.src).split(".")[-1] not in ("join", "resolve") or text(args[0], self.src) not in HERE \
                or any(a.type != "string" for a in args[1:]):
            return None
        here = posixpath.dirname(self.fx.file.path)
        d = posixpath.normpath(posixpath.join(here, *(unquote(text(a, self.src)) for a in args[1:])))
        return None if d.startswith("..") else "" if d == "." else d

    def publish_autoloads(self, is_app) -> None:
        for d, key, prefix, folders in self.__dict__.get("autoloads", ()):
            for target, pp in self.mounts.targets(key, self._global, is_app):
                self.out.publish(AUTOLOAD, d, (target, pp.rstrip("/") + prefix.rstrip("/"), folders))


def compose_autoloads(out: HttpResult, view, mount_rule: str) -> None:
    """Each file under an autoloaded directory: the router its default export receives, mounted where the
    registration leads, under its folders' path."""
    loads = out.facts.get(AUTOLOAD, {})
    for f in view.files_under(list(loads)) if loads and view is not None else ():
        for d in (d for d in loads if f.startswith(d + "/" if d else "")):
            folder = posixpath.dirname(f)[len(d):] if d else "/" + posixpath.dirname(f)
            for target, prefix, folders in set(loads[d]):
                out.publish(f"{mount_rule}.edge", f"param:{f}:default:0",
                            (target, prefix + (folder.rstrip("/") if folders and folder != "/" else "")))


def _route_paths(rel_dir: str) -> list[str]:
    """The paths a route's folders give; none under a `_private` folder."""
    parts, folders = [], [s for s in rel_dir.split("/") if s]
    for f in folders:
        if f.startswith("_"):
            return []
        if f.startswith("(") and f.endswith(")") or f.startswith("@"):
            continue
        m = re.fullmatch(r"\[{1,2}(?:\.\.\.)?(\w+)\]{1,2}", f)
        parts.append("{" + m.group(1) + "}" if m else f)
    path = "/" + "/".join(parts)
    optional = bool(folders) and folders[-1].startswith("[[")
    return [path, "/" + "/".join(parts[:-1])] if optional else [path]
