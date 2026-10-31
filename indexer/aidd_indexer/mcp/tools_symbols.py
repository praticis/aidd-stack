"""`find_symbol`, `who_calls` and `symbol_context`: finding symbols and what is around one."""

from __future__ import annotations

import re
from typing import Any

from .store import LUCENE_SPECIAL, MAX_ROWS, AtlasError, Store


def _word_pattern(word: str) -> str:
    """Regex (Neo4j `=~`, whole name) for `word` as a whole word of an identifier: camelCase,
    PascalCase, snake_case or ACRONYM parts — 'backoff' finds RetryBackoff, backoffDelay and
    retry_backoff, not Backoffice."""
    if not re.fullmatch(r"[A-Za-z0-9]+", word):
        raise AtlasError("match='word' takes a single identifier word (letters and digits); use match='regex' otherwise")
    low, cap, up = word.lower(), word[:1].upper() + word[1:].lower(), word.upper()
    return ("(?s)(?:"
            f"{low}(?:[A-Z0-9_].*)?"                     # leading lower word: backoffDelay, backoff_x
            f"|.*{cap}(?:[A-Z0-9_].*)?"                  # PascalCase part: RetryBackoff, BackoffDelay
            f"|(?:.*[^A-Z])?{up}(?:[^a-z].*)?"           # acronym part: HTTPClient, NewHTTP
            f"|(?i:(?:.*_)?{low}(?:_.*)?)"               # snake_case part: retry_backoff
            ")")


def _fulltext_query(text: str) -> str:
    """Lucene query for `symbol_fulltext`: exact term OR prefix, special chars escaped."""
    terms = [LUCENE_SPECIAL.sub(r"\\\1", t) for t in text.split() if t]
    if not terms:
        raise AtlasError("empty query")
    parts = []
    for t in terms:
        parts.append(f"{t}")
        parts.append(f"{t}*")
    return " OR ".join(parts)


def _symbol(s: Store, symbol: str, repo: str | None, ref: str | None) -> dict[str, Any]:
    """Resolve `symbol` (id, qualified_name, the tail of one — `Class.Method` — or bare name) to exactly
    one Symbol node. The tail is tried only when nothing matches exactly."""
    if repo:
        ref = s.resolve_ref(repo, ref)
    rows = _symbol_rows(s, symbol, repo, ref, "sy.id = $symbol OR sy.qualified_name = $symbol OR sy.name = $symbol")
    if not rows and "." in symbol:            # `CreateTodoCommandHandler.Handle`: a tail on a `.`/`:` boundary
        rows = _symbol_rows(s, symbol, repo, ref,
                            "sy.qualified_name ENDS WITH '.' + $symbol OR sy.qualified_name ENDS WITH ':' + $symbol")
    if not rows:
        raise AtlasError(f"symbol '{symbol}' not found" + (f" in {repo}@{ref}" if repo else "") +
                         " as an id, a qualified name, its `Class.Method` tail or a bare name — this says nothing about"
                         " how the file was parsed: look it up with find_symbol (match: word), or name the repo/ref")
    if len(rows) > 1:
        opts = "; ".join(f"{r['id']}" for r in rows)
        raise AtlasError(f"'{symbol}' is ambiguous ({len(rows)} matches). Use one of the ids: {opts}")
    return rows[0]

def _symbol_rows(s: Store, symbol: str, repo: str | None, ref: str | None, match: str) -> list[dict[str, Any]]:
    return s.read(f"""
            MATCH (sy:Symbol {{tenant: $tenant}})
            WHERE ({match})
              AND ($repo IS NULL OR sy.repo = $repo)
            MATCH (snap:Snapshot {{tenant: $tenant, repo: sy.repo, ref: sy.ref}})
            WHERE ($ref IS NOT NULL AND sy.ref = $ref) OR ($ref IS NULL AND coalesce(snap.ephemeral, false) = false)
            MATCH (f:File)-[:CONTAINS]->(sy)
            RETURN sy.id AS id, sy.repo AS repo, sy.ref AS ref, sy.kind AS kind, sy.name AS name,
                   sy.qualified_name AS qualified_name, f.path AS file, sy.line_start AS line_start,
                   sy.line_end AS line_end, sy.signature AS signature, sy.doc AS doc,
                   sy.visibility AS visibility, sy.is_entry_point AS entry_point, sy.role AS role
            LIMIT 6
        """, symbol=symbol, repo=repo, ref=ref)


_OVERRIDING = {"overrides": "(:Symbol {id: $id})-[:OVERRIDES]->(o:Symbol)",
               "overridden_by": "(:Symbol {id: $id})<-[:OVERRIDES]-(o:Symbol)"}


def _overriding(s: Store, symbol_id: str, pattern: str) -> list[dict[str, Any]]:
    return s.read(f"""
        MATCH {pattern}
        MATCH (f:File)-[:CONTAINS]->(o)
        RETURN o.id AS id, o.qualified_name AS qualified_name, f.path AS file, o.line_start AS line
        ORDER BY file, line, id LIMIT $limit
    """, id=symbol_id, limit=MAX_ROWS)


def register(mcp, st) -> None:
    @mcp.tool()
    def find_symbol(query: str, repo: str | None = None, ref: str | None = None,
                    kind: str | None = None, role: str | None = None, limit: int = 20,
                    match: str = "fuzzy", tenant: str | None = None) -> list[dict[str, Any]]:
        """Search symbols (functions, methods, types, constants, package variables...).
        `match` picks how `query` is compared:
          fuzzy (default) — full text over names, qualified names, signatures and docstrings, topped up
                  with substring matches on the name: broad, good to discover ('backoff' also brings
                  'Backoffice')
          word  — `query` is a whole word of the name, camelCase/snake_case aware ('backoff' finds
                  RetryBackoff and retry_backoff, not Backoffice)
          exact — name or qualified name equals `query`
          regex — Java regex searched in the name (`^`/`$` anchor it): '^Err[A-Z]', 'Pix(Devolution|Refund)'
        Without `ref`, only default branches are searched; name a `ref` to search a feature branch.
        `kind` filters e.g. function|method|struct|interface|const|var; `role` filters by what a
        convention says the type is (`command-handler`, `validator`... — see `repo_map.roles`). With a
        `role`, `query` "*" lists every element of it."""
        s = st(tenant)
        if repo:
            ref = s.resolve_ref(repo, ref)
        if match not in ("fuzzy", "word", "exact", "regex"):
            raise AtlasError(f"unknown match '{match}' — use fuzzy, word, exact or regex")
        if match != "fuzzy" and query.strip() not in ("", "*"):
            text = query.strip()
            if match == "word":
                cond, pattern = "sy.name =~ $pattern", _word_pattern(text)
            elif match == "regex":
                try:
                    re.compile(text)
                except re.error as e:
                    raise AtlasError(f"invalid regex: {e}") from None
                cond, pattern = "sy.name =~ $pattern", f"(?s).*(?:{text}).*"
            else:
                cond, pattern = "(sy.name = $text OR sy.qualified_name = $text)", None
            return s.read(f"""
                MATCH (sy:Symbol {{tenant: $tenant}})
                WHERE {cond}
                  AND ($repo IS NULL OR sy.repo = $repo)
                  AND ($kind IS NULL OR sy.kind = $kind)
                  AND ($role IS NULL OR sy.role = $role)
                MATCH (snap:Snapshot {{tenant: $tenant, repo: sy.repo, ref: sy.ref}})
                WHERE ($ref IS NOT NULL AND sy.ref = $ref) OR ($ref IS NULL AND coalesce(snap.ephemeral, false) = false)
                MATCH (f:File)-[:CONTAINS]->(sy)
                RETURN sy.id AS id, sy.repo AS repo, sy.ref AS ref, sy.kind AS kind, sy.name AS name,
                       sy.qualified_name AS qualified_name, f.path AS file, sy.line_start AS line,
                       sy.signature AS signature, sy.is_entry_point AS entry_point, sy.role AS role, 1.0 AS score
                ORDER BY size(sy.name), sy.repo, f.path, sy.line_start LIMIT $limit
            """, text=text, pattern=pattern, repo=repo, ref=ref, kind=kind, role=role, limit=min(limit, MAX_ROWS))
        if role and query.strip() in ("", "*"):
            return s.read("""
                MATCH (sy:Symbol {tenant: $tenant, role: $role})
                WHERE ($repo IS NULL OR sy.repo = $repo) AND ($kind IS NULL OR sy.kind = $kind)
                MATCH (snap:Snapshot {tenant: $tenant, repo: sy.repo, ref: sy.ref})
                WHERE ($ref IS NOT NULL AND sy.ref = $ref) OR ($ref IS NULL AND coalesce(snap.ephemeral, false) = false)
                MATCH (f:File)-[:CONTAINS]->(sy)
                RETURN sy.id AS id, sy.repo AS repo, sy.ref AS ref, sy.kind AS kind, sy.name AS name,
                       sy.qualified_name AS qualified_name, f.path AS file, sy.line_start AS line,
                       sy.signature AS signature, sy.is_entry_point AS entry_point, sy.role AS role, 1.0 AS score
                ORDER BY sy.repo, f.path, sy.line_start LIMIT $limit
            """, role=role, repo=repo, ref=ref, kind=kind, limit=min(limit, MAX_ROWS))
        rows = s.read("""
            CALL db.index.fulltext.queryNodes('symbol_fulltext', $q) YIELD node AS sy, score
            WHERE sy.tenant = $tenant
              AND ($repo IS NULL OR sy.repo = $repo)
              AND ($kind IS NULL OR sy.kind = $kind)
              AND ($role IS NULL OR sy.role = $role)
            MATCH (snap:Snapshot {tenant: $tenant, repo: sy.repo, ref: sy.ref})
            WHERE ($ref IS NOT NULL AND sy.ref = $ref) OR ($ref IS NULL AND coalesce(snap.ephemeral, false) = false)
            MATCH (f:File)-[:CONTAINS]->(sy)
            RETURN sy.id AS id, sy.repo AS repo, sy.ref AS ref, sy.kind AS kind, sy.name AS name,
                   sy.qualified_name AS qualified_name, f.path AS file, sy.line_start AS line,
                   sy.signature AS signature, sy.is_entry_point AS entry_point, sy.role AS role, round(score, 2) AS score
            ORDER BY score DESC LIMIT $limit
        """, q=_fulltext_query(query), repo=repo, ref=ref, kind=kind, role=role, limit=min(limit, MAX_ROWS))
        # Lucene matches whole terms and prefixes ('Handler' → 'Handler', 'HandlerFunc'), not
        # suffixes ('AuthHandler'). Top up with a case-insensitive substring pass on the name.
        if len(rows) < limit and " " not in query.strip():
            seen = {r["id"] for r in rows}
            extra = s.read("""
                MATCH (sy:Symbol {tenant: $tenant})
                WHERE toLower(sy.name) CONTAINS toLower($text)
                  AND ($repo IS NULL OR sy.repo = $repo)
                  AND ($kind IS NULL OR sy.kind = $kind)
                  AND ($role IS NULL OR sy.role = $role)
                MATCH (snap:Snapshot {tenant: $tenant, repo: sy.repo, ref: sy.ref})
                WHERE ($ref IS NOT NULL AND sy.ref = $ref) OR ($ref IS NULL AND coalesce(snap.ephemeral, false) = false)
                MATCH (f:File)-[:CONTAINS]->(sy)
                RETURN sy.id AS id, sy.repo AS repo, sy.ref AS ref, sy.kind AS kind, sy.name AS name,
                       sy.qualified_name AS qualified_name, f.path AS file, sy.line_start AS line,
                       sy.signature AS signature, sy.is_entry_point AS entry_point, sy.role AS role, 0.0 AS score
                ORDER BY size(sy.name), sy.name LIMIT $limit
            """, text=query.strip(), repo=repo, ref=ref, kind=kind, role=role, limit=min(limit, MAX_ROWS))
            rows += [r for r in extra if r["id"] not in seen][: limit - len(rows)]
        return rows
    @mcp.tool()
    def who_calls(symbol: str, repo: str | None = None, ref: str | None = None, limit: int = 50, tenant: str | None = None) -> dict[str, Any]:
        """Incoming calls: which symbols (and files) call `symbol`. `symbol` may be a symbol id from
        find_symbol, a qualified name (pkg.Type.Method), its `Type.Method` tail or a bare name when unambiguous. Calls are
        resolved by name within the repo (strategy on each edge) — treat cross-package hits as likely, not proven.
        On a type (class/interface/struct), `inherited` callers use a method it gets from a package base
        (`method` says which: `repo.CreateAsync()` on `ITodoRepository : IBaseRepository<T>`).
        On a method, `dispatched_callers` make a dispatching call to a method it overrides or implements
        (`via`), on a receiver that may hold an instance which runs it; `overrides` lists those methods, and
        `overridden_by` the methods that may run instead of it, whose callers never run it."""
        s = st(tenant)
        target = _symbol(s, symbol, repo, ref)
        cap = min(limit, MAX_ROWS)
        callers = s.read("""
            MATCH (caller)-[c:CALLS]->(:Symbol {id: $id})
            OPTIONAL MATCH (f:File)-[:CONTAINS]->(caller)
            RETURN caller.id AS id, labels(caller)[0] AS type, coalesce(caller.qualified_name, caller.path) AS qualified_name,
                   caller.kind AS kind, coalesce(f.path, caller.path) AS file, c.line AS line, c.strategy AS strategy, c.method AS method
            ORDER BY file, line LIMIT $limit
        """, id=target["id"], limit=cap)
        dispatched = s.read("""
            MATCH (:Symbol {id: $id})-[r:OVERRIDES]->(o:Symbol)<-[c:CALLS]-(caller)
            WHERE c.virtual AND (c.receivers IS NULL OR any(t IN c.receivers WHERE t IN r.receivers))
            OPTIONAL MATCH (f:File)-[:CONTAINS]->(caller)
            RETURN caller.id AS id, labels(caller)[0] AS type,
                   coalesce(caller.qualified_name, caller.path) AS qualified_name, caller.kind AS kind,
                   coalesce(f.path, caller.path) AS file, c.line AS line, c.strategy AS strategy, o.qualified_name AS via
            ORDER BY file, line, via LIMIT $limit
        """, id=target["id"], limit=cap)
        return {"symbol": target, "callers": callers, "caller_count": len(callers), "dispatched_callers": dispatched,
                "dispatched_caller_count": len(dispatched),
                **{k: _overriding(s, target["id"], pattern) for k, pattern in _OVERRIDING.items()}}

    @mcp.tool()
    def symbol_context(symbol: str, repo: str | None = None, ref: str | None = None, limit: int = 30, tenant: str | None = None) -> dict[str, Any]:
        """Everything the graph knows around one symbol: definition (file, lines, signature, doc),
        its container (class/struct) and members, what it calls, who calls it, and what its file
        imports. The right tool before editing a function or estimating impact."""
        s = st(tenant)
        sy = _symbol(s, symbol, repo, ref)
        base = dict(id=sy["id"], limit=min(limit, MAX_ROWS))
        parent = s.read("MATCH (p:Symbol)-[:CONTAINS]->(:Symbol {id: $id}) RETURN p.id AS id, p.kind AS kind, p.qualified_name AS qualified_name", **base)
        members = s.read("MATCH (:Symbol {id: $id})-[:CONTAINS]->(m:Symbol) RETURN m.id AS id, m.kind AS kind, m.name AS name, m.signature AS signature ORDER BY m.line_start LIMIT $limit", **base)
        callees = s.read("""
            MATCH (:Symbol {id: $id})-[c:CALLS]->(t:Symbol)
            MATCH (f:File)-[:CONTAINS]->(t)
            RETURN t.id AS id, t.kind AS kind, t.qualified_name AS qualified_name, f.path AS file, c.line AS line, c.strategy AS strategy, c.method AS method
            ORDER BY line LIMIT $limit
        """, **base)
        callers = s.read("""
            MATCH (caller)-[c:CALLS]->(:Symbol {id: $id})
            OPTIONAL MATCH (f:File)-[:CONTAINS]->(caller)
            RETURN caller.id AS id, labels(caller)[0] AS type, coalesce(caller.qualified_name, caller.path) AS qualified_name,
                   coalesce(f.path, caller.path) AS file, c.line AS line, c.strategy AS strategy, c.method AS method
            ORDER BY file, line LIMIT $limit
        """, **base)
        imports = s.read("""
            MATCH (f:File)-[:CONTAINS]->(:Symbol {id: $id})
            MATCH (f)-[i:IMPORTS]->(t)
            RETURN labels(t)[0] AS type, coalesce(t.name, t.path) AS target, i.spec AS spec
            ORDER BY type, target, spec LIMIT $limit
        """, **base)
        return {"symbol": sy, "parent": parent[0] if parent else None, "members": members,
                "calls": callees, "called_by": callers, "file_imports": imports}
