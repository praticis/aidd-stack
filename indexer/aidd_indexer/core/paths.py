"""HTTP path templates: normalization and the comparison key shared by the extractor, the graph
writer and the MCP server. Language-agnostic — every framework's placeholder syntax collapses to
`{name}` here, and `path_key` collapses names to `{param}` so `/v1/users/{id}` == `/v1/users/{userId}`.
"""

from __future__ import annotations

import re

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
VERB_BY_NAME = {v.lower(): v for v in HTTP_METHODS} | {v.capitalize(): v for v in HTTP_METHODS} | {v: v for v in HTTP_METHODS}

PATH_LITERAL = re.compile(r"^/[A-Za-z0-9_\-./{}:%$*\[\]]*$")
REL_PATH_LITERAL = re.compile(r"^(api|v\d+)/[A-Za-z0-9_\-./{}:%$*\[\]?=&]*$")        # C#/JS clients often omit the leading slash
URL_LITERAL = re.compile(r"^https?://[^/\s]+(/.*)?$")
ENV_URL_NAME = re.compile(r"^[A-Z][A-Z0-9_]*(URL|HOST|ENDPOINT|BASE_URL|ADDR|BASEURL)$")

_NOT_A_PATH_HEAD = {"http", "https", "utf", "bearer", "basic", "true", "false"}
# `application/json`, `image/svg+xml`: a MIME type is two tokens — `application/{id}` and `message/{id}/read` are paths
MIME_TYPE = re.compile(r"^(application|text|image|multipart|audio|video|message|font|model)/[A-Za-z0-9.+\-]+$", re.I)


def is_url_literal(s: str) -> bool:
    """`https://host`, or `https://host/path` with a path a route could have (placeholders masked, the query aside):
    `https://host/admin/{token}god_mode=true` is not one."""
    m = URL_LITERAL.match(s)
    if m is None:
        return False
    tail = mask_placeholders(m.group(1) or "/").split("?", 1)[0].split("#", 1)[0]
    return PATH_LITERAL.match(tail) is not None


def unquote(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^[fFrRbBuU$@]{1,3}(?=[\"'`])", "", s)     # f"..", $"..", @"..", rb".."
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'`":
        return s[1:-1]
    return s


# Express 4's regex after a parameter (`/:pk(\d+)`, `/:pk(${UUID_REGEX})`); not ASP.NET's `{name:minlength(1)}`
EXPRESS_CONSTRAINT = re.compile(r"(?<!\w):([A-Za-z_][A-Za-z0-9_]*)\((?:[^()]|\([^()]*\))*\)")
PLACEHOLDER = re.compile(r"\{(?:[^{}]|\{[^{}]*\})*\}|<[^<>]*>")        # a regex constraint may hold braces: {id:[0-9]{4}}
_ALTERNATIVES = re.compile(r"(?:(?<=/)|^)\{[A-Za-z_]\w*\s*:\s*\(?((?:[\w.-]+\|)+[\w.-]+|[\w.-]+(?=\(\?:\\*/\)\?))\)?"
                           r"(?:\(\?:\\*/\)\?)?\}(?=/|$)")        # a whole segment: `{sha}.{diffType:diff|patch}` stays a parameter


def expand_alternatives(pattern: str) -> list[str]:
    """`/{syncable_type:teams|channels}/x` → `/teams/x`, `/channels/x`: a whole segment whose regex lists literal words
    stands for each of them (gorilla, chi); `{ws:websocket(?:\\/)?}` is the word itself."""
    m = _ALTERNATIVES.search(pattern)
    if m is None:
        return [pattern]
    head, tail = pattern[:m.start()], pattern[m.end():]
    return [x for alt in m.group(1).split("|") for x in expand_alternatives(head + alt + tail)][:16]


def mask_placeholders(pattern: str) -> str:
    """Every placeholder → `{p}`, so that what a route placeholder may hold — constraints and converters
    (`{id:int?}`, `{name:minlength(1)}`, `{slug:[a-z-]+}`, `<int:id>`, `<any(a, b):page>`) and optional
    markers (`:id?`) — does not make the literal check reject the whole pattern."""
    masked = re.sub(r"(?<![}A-Za-z0-9]):([A-Za-z_][A-Za-z0-9_]*)\?", r":\1", PLACEHOLDER.sub("{p}", pattern))
    return EXPRESS_CONSTRAINT.sub(r":\1", masked)


def path_key(path: str) -> str:
    """Comparison key: every placeholder becomes {param} — `/v1/users/{id}` == `/v1/users/{param}`."""
    return re.sub(r"\{[^}]*\}", "{param}", path)


def normalize_path(path: str) -> str:
    """Route/template → canonical `/a/{param}/b`. Idempotent."""
    p = path.strip()
    m = URL_LITERAL.match(p)
    if m:
        p = m.group(1) or "/"
    p = re.sub(r"\{([./]?):([A-Za-z_][A-Za-z0-9_]*)\}", r"\1{\2}", p)   # Express 5 optional group {:q}, {.:ext}, {/:id} → its parameter
    p = re.sub(r"\{/\*([A-Za-z_][A-Za-z0-9_]*)\}", r"/*\1", p)       # its optional wildcard {/*path} (Express 5, @koa/router)
    p = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)\{(?:[^{}]|\{[^{}]*\})*\}", r"{\1}", p)   # Hono :id{[0-9]+}, before the ?
    p = EXPRESS_CONSTRAINT.sub(r"{\1}", p)                         # Express :pk(\d+), a regex in parentheses
    p = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\s*:(?:[^{}]|\{[^{}]*\})*\}", r"{\1}", p)   # {id:int}, {id:[0-9]{4}} → {id}: before
    #                                                             the query split — a regex constraint may hold `?`
    p = re.sub(r"\{([^{}]*?)\?\}", r"{\1}", p)                  # optional placeholder {id?}, {id:int?} — before the query split
    p = re.sub(r"(?<![}A-Za-z0-9]):([A-Za-z_][A-Za-z0-9_]*)\?", r":\1", p)   # optional :id? (express, gin)
    p = p.split("?", 1)[0].split("#", 1)[0]
    p = re.sub(r"%[sdvq]", "{param}", p)                          # Sprintf verbs
    p = re.sub(r"\$\{[^}]*\}", "{param}", p)                      # JS template literals
    p = re.sub(r"\{\*+([A-Za-z_][A-Za-z0-9_]*)\}", r"{\1}", p)   # {*rest} (ASP.NET catch-all)
    p = re.sub(r"<(?:[^<>:]+:)?([A-Za-z_][A-Za-z0-9_]*)>", r"{\1}", p)  # <int:id>, <any(a, b):page> (Flask/Werkzeug)
    # :id (gin, express, echo), after `/`, `-`, `.` or `_`; glued to a name or a placeholder it is a custom verb of the
    # Google API style (`/api/ai:transcribe`, `{name}:cancel`, Azure's `transcriptions:transcribe`), never a parameter
    p = re.sub(r"(?<![}A-Za-z0-9]):([A-Za-z_][A-Za-z0-9_]*)\??", r"{\1}", p)
    p = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)(\.\.\.)?\}", r"{\1}", p)  # {id...} → {id}
    p = re.sub(r"\{\d+\}", "{param}", p)                             # string.Format("{0}")
    p = re.sub(r"\[controller\]", "{controller}", p, flags=re.I)  # ASP.NET token (resolved later by the linker)
    p = re.sub(r"\[action\]", "{action}", p, flags=re.I)
    p = re.sub(r"\*\w*", "{rest}", p)                             # wildcards
    p = re.sub(r"^\{[^}]*\}(?=/)", "", p)                         # leading base-URL placeholder: {base}/v1 → /v1
    p = re.sub(r"/{2,}", "/", p)
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    if not p.startswith("/"):
        p = "/" + p
    return p


def looks_like_rel_path(s: str) -> bool:
    """`items/{id}`, `catalog/brands?x=1`, `application/{id}` — but not `application/json` or `a/b.txt`."""
    if not re.match(r"^[A-Za-z][A-Za-z0-9_\-]*/[A-Za-z0-9_\-./{}?=&:%]*$", s):
        return False
    head = s.split("/", 1)[0].lower()
    return head not in _NOT_A_PATH_HEAD and not MIME_TYPE.match(s) and not re.search(r"\.(json|xml|txt|html|js|css|png|jpg|svg|ya?ml|csv|pdf)$", s, re.I)


def has_literal_segment(path: str) -> bool:
    """A segment with a name in it — `/{param}/{param}/,` (a cache key joined with commas) has none."""
    return any(seg and not seg.startswith("{") and re.search(r"[A-Za-z0-9]", seg) for seg in path.split("/"))
