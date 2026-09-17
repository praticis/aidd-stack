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

_NOT_A_PATH_HEAD = {"application", "text", "image", "multipart", "audio", "video", "message", "font", "model",
                    "http", "https", "utf", "bearer", "basic", "true", "false"}


def unquote(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^[fFrRbBuU$@]{1,3}(?=[\"'`])", "", s)     # f"..", $"..", @"..", rb".."
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'`":
        return s[1:-1]
    return s


def path_key(path: str) -> str:
    """Comparison key: every placeholder becomes {param} — `/v1/users/{id}` == `/v1/users/{param}`."""
    return re.sub(r"\{[^}]*\}", "{param}", path)


def normalize_path(path: str) -> str:
    """Route/template → canonical `/a/{param}/b`. Idempotent."""
    p = path.strip()
    m = URL_LITERAL.match(p)
    if m:
        p = m.group(1) or "/"
    p = p.split("?", 1)[0].split("#", 1)[0]
    p = re.sub(r"%[sdvq]", "{param}", p)                          # Sprintf verbs
    p = re.sub(r"\$\{[^}]*\}", "{param}", p)                      # JS template literals
    p = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\s*:[^}]*\}", r"{\1}", p)   # {id:int} (ASP.NET) → {id}
    p = re.sub(r"\{\*+([A-Za-z_][A-Za-z0-9_]*)\}", r"{\1}", p)   # {*rest} (ASP.NET catch-all)
    p = re.sub(r"<(?:[a-z_]+:)?([A-Za-z_][A-Za-z0-9_]*)>", r"{\1}", p)  # <int:id> (Flask)
    p = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)\??", r"{\1}", p)      # :id (gin, express, echo)
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
    """`items/{id}`, `catalog/brands?x=1` — but not `application/json` or `a/b.txt`."""
    if not re.match(r"^[A-Za-z][A-Za-z0-9_\-]*/[A-Za-z0-9_\-./{}?=&:%]*$", s):
        return False
    head = s.split("/", 1)[0].lower()
    return head not in _NOT_A_PATH_HEAD and not re.search(r"\.(json|xml|txt|html|js|css|png|jpg|svg|ya?ml|csv|pdf)$", s, re.I)


def has_literal_segment(path: str) -> bool:
    return any(seg and not seg.startswith("{") for seg in path.split("/"))
