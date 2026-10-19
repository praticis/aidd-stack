"""Deterministic node ids — neo4j/SCHEMA.md §4.

Readable, no hashes, so MERGE is idempotent and the Browser stays debuggable.
"""


def repo(tenant: str, repo: str) -> str:
    return f"{tenant}/{repo}"


def snapshot(tenant: str, repo: str, ref: str) -> str:
    return f"{tenant}/{repo}@{ref}"


def module(tenant: str, repo: str, ref: str, path: str) -> str:
    return f"{tenant}/{repo}@{ref}/mod/{path or '.'}"


def file(tenant: str, repo: str, ref: str, path: str) -> str:
    return f"{tenant}/{repo}@{ref}/file/{path}"


def symbol(tenant: str, repo: str, ref: str, qualified_name: str, kind: str) -> str:
    return f"{tenant}/{repo}@{ref}/sym/{qualified_name}#{kind}"


def package(tenant: str, ecosystem: str, name: str) -> str:
    return f"{tenant}/pkg/{ecosystem}/{name}"


def index_run(tenant: str, repo: str, ref: str, started_iso: str) -> str:
    return f"{tenant}/{repo}@{ref}/run/{started_iso}"


def service(tenant: str, name: str) -> str:
    return f"{tenant}/svc/{name}"


def http_endpoint(tenant: str, service_name: str, method: str, path_key: str, app: str = "") -> str:
    """Keyed by `path_key` (placeholders normalized to `{param}`): renaming `{id}` to `{userId}`
    on a branch is the same route, not a second endpoint. The display `path` stays an attribute.
    `app`: the module that declares the route, when the repo's routes come from more than one, so the
    same route in two apps of a repo is two endpoints."""
    scope = f"{tenant}/svc/{service_name}" + (f"/app/{app}" if app else "")
    return f"{scope}/http/{method} {path_key}"


def http_call(tenant: str, repo: str, ref: str, file_path: str, line: int) -> str:
    return f"{tenant}/{repo}@{ref}/httpcall/{file_path}:{line}"


def violation(tenant: str, repo: str, ref: str, convention: str, rule: str, file_path: str, line: int) -> str:
    return f"{tenant}/{repo}@{ref}/violation/{convention}.{rule}/{file_path}:{line}"
