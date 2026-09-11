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
