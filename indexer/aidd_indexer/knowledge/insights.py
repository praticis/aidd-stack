"""Insight notes and the project index's knowledge block."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .vault import CONTRACT, KnowledgeError, join_frontmatter, replace_block, split_frontmatter, write_atomic

SEVERITIES = ("low", "medium", "high", "critical")
STATUS_ORDER = ("enforced", "accepted", "recurring", "observed")       # index order; archived is not listed
RULES = ("accepted", "enforced")
SOURCES = ("pr-review", "review", "harness", "sarif", "sonar", "incident", "session", "scan")
EVIDENCE_KEYS = ("at", "source", "repo", "ref", "sha", "location", "link", "tool", "note")
APPLIES_KEYS = ("files", "roles", "symbols")
MAX_EVIDENCE = 20
SHARED = "shared"


def today() -> str:
    return date.today().isoformat()


def as_date(value: str) -> date | str:
    """Frontmatter dates as YAML dates (unquoted, sortable in Obsidian), when they parse."""
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return value


@dataclass
class Insight:
    path: Path
    rel: str                     # vault-relative, posix
    meta: dict[str, Any]
    body: str

    @property
    def status(self) -> str:
        return str(self.meta.get("status") or "observed")

    @property
    def scope(self) -> str:
        return str(self.meta.get("scope") or "repo")

    def section(self, title: str) -> str:
        m = re.search(rf"^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)", self.body, re.S | re.M)
        return m.group(1).strip() if m else ""

    def applies(self, files: list[str], roles: list[str], symbols: list[str]) -> bool:
        """No filter, or a general insight (empty `applies_to`), or any overlap with what is being touched."""
        if not (files or roles or symbols):
            return True
        a = self.meta.get("applies_to") or {}
        globs, iroles, isyms = a.get("files") or [], a.get("roles") or [], a.get("symbols") or []
        if not (globs or iroles or isyms):
            return True
        if any(fnmatch.fnmatch(f, g) for f in files for g in globs):
            return True
        if set(roles) & set(iroles):
            return True
        return any(s == i or s.endswith("." + i) or i.endswith("." + s) for s in symbols for i in isyms)

    def view(self) -> dict[str, Any]:
        m = self.meta
        return {"id": m.get("id"), "topic": m.get("topic"), "summary": m.get("summary"), "status": self.status,
                "severity": m.get("severity"), "scope": self.scope, "occurrences": m.get("occurrences"),
                "last_seen": str(m.get("last_seen") or ""), "applies_to": m.get("applies_to") or {},
                "what_to_do": self.section("What to do instead"), "rule": m.get("rule"), "note": self.rel}


class Layout:
    """Where things live under the vault root (`<tenant>/knowledge/...`)."""

    def __init__(self, root: Path):
        self.root = root

    def knowledge(self, tenant: str) -> Path:
        return self.root / tenant / "knowledge"

    def insights_dir(self, tenant: str, owner: str) -> Path:
        return self.knowledge(tenant) / owner / "insights"

    def index_page(self, tenant: str, repo: str) -> Path:
        return self.knowledge(tenant) / repo / f"{repo}.md"

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def load(self, path: Path) -> Insight | None:
        try:
            meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            return None
        if meta.get("type") != "insight":
            return None
        return Insight(path=path, rel=self.rel(path), meta=meta, body=body)

    def notes(self, tenant: str, owner: str) -> list[Insight]:
        d = self.insights_dir(tenant, owner)
        if not d.is_dir():
            return []
        return [i for p in sorted(d.glob("*.md")) if (i := self.load(p)) is not None]

    def indexed_repos(self, tenant: str) -> list[str]:
        k = self.knowledge(tenant)
        if not k.is_dir():
            return []
        return sorted(d.name for d in k.iterdir() if d.is_dir() and d.name != SHARED and (d / f"{d.name}.md").exists())


def check_evidence(evidence: Any, repo: str) -> list[dict[str, str]]:
    if not isinstance(evidence, list) or not evidence:
        raise KnowledgeError("evidence is required: at least one entry with a `source` "
                             f"({', '.join(SOURCES)}) — an insight without provenance is not recorded")
    out = []
    for e in evidence:
        if not isinstance(e, dict):
            raise KnowledgeError("each evidence entry is an object (source, location, link, note, ...)")
        unknown = set(e) - set(EVIDENCE_KEYS)
        if unknown:
            raise KnowledgeError(f"unknown evidence keys {sorted(unknown)} (allowed: {', '.join(EVIDENCE_KEYS)})")
        if e.get("source") not in SOURCES:
            raise KnowledgeError(f"evidence source must be one of {', '.join(SOURCES)} (got {e.get('source')!r})")
        entry = {k: str(e[k]) for k in EVIDENCE_KEYS if e.get(k) not in (None, "")}
        entry.setdefault("at", today())
        entry.setdefault("repo", repo)
        out.append({k: entry[k] for k in EVIDENCE_KEYS if k in entry})
    return out


def check_applies_to(applies_to: Any) -> dict[str, list[str]]:
    if applies_to in (None, {}):
        return {}
    if not isinstance(applies_to, dict) or set(applies_to) - set(APPLIES_KEYS):
        raise KnowledgeError(f"applies_to takes {', '.join(APPLIES_KEYS)} (lists of file globs, convention roles, "
                             "qualified symbol names)")
    out = {}
    for k in APPLIES_KEYS:
        v = applies_to.get(k) or []
        if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v):
            raise KnowledgeError(f"applies_to.{k} must be a list of strings")
        if v:
            out[k] = v
    return out


def note_text(meta: dict[str, Any], what_happened: str, what_to_do: str) -> str:
    body = (f"\n# {meta['summary']}\n\n## What happened\n{what_happened.strip()}\n\n"
            f"## What to do instead\n{what_to_do.strip()}\n\n## Notes\n")
    return join_frontmatter(meta, body)


def save(insight: Insight) -> None:
    """Frontmatter rewritten, body kept as it is on disk (people may have edited it)."""
    write_atomic(insight.path, join_frontmatter(insight.meta, insight.body))


def _alias(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).replace("|", "/").replace("[", "(").replace("]", ")").strip()


def render_knowledge(own: list[Insight], shared: list[Insight], topics: list[str]) -> str:
    live = [(i, False) for i in own if i.status != "archived"] + [(i, True) for i in shared if i.status != "archived"]
    lines = ["## Knowledge", "_Generated from the insight notes — do not edit here._"]
    if not live:
        return "\n".join(lines + ["", "_No insights recorded yet._"])
    order = list(topics) + sorted({str(i.meta.get("topic")) for i, _ in live} - set(topics))
    for topic in order:
        items = [(i, s) for i, s in live if i.meta.get("topic") == topic]
        if not items:
            continue
        # status, then occurrences descending, then last_seen descending (stable sorts, last key first)
        items.sort(key=lambda x: str(x[0].meta.get("last_seen") or ""), reverse=True)
        items.sort(key=lambda x: (STATUS_ORDER.index(x[0].status) if x[0].status in STATUS_ORDER else 9,
                                  -int(x[0].meta.get("occurrences") or 1)))
        lines += ["", f"### {topic.replace('-', ' ').capitalize()}"]
        for i, is_shared in items:
            status = f"**{i.status}**" if i.status in RULES else i.status
            target = i.rel[:-3] if i.rel.endswith(".md") else i.rel
            lines.append(f"- [[{target}|{_alias(i.meta.get('summary', ''))}]]{' (shared)' if is_shared else ''}"
                         f" — {status} · {int(i.meta.get('occurrences') or 1)}× · last {i.meta.get('last_seen')}")
    return "\n".join(lines)


def write_index_block(layout: Layout, tenant: str, repo: str, block: str) -> bool:
    """Replace the `aidd:knowledge` block of the repo's index page, creating the page when there is none.
    Only the block changes; the frontmatter and everything else belong to `scan` and to people."""
    page = layout.index_page(tenant, repo)
    if page.exists():
        text = page.read_text(encoding="utf-8")
        meta, body = split_frontmatter(text)
        has_fm = bool(meta)                   # unreadable frontmatter stays in the body, untouched
    else:
        meta = {"type": "project-index", "contract": CONTRACT, "tenant": tenant, "project": repo,
                "atlas": None, "updated": as_date(today())}
        body, has_fm, text = f"\n# {repo}\n", True, ""
    new_body = replace_block(body, "knowledge", block, after=("policy", "scan"))
    new_text = join_frontmatter(meta, new_body) if has_fm else new_body
    if new_text == text:
        return False
    write_atomic(page, new_text)
    return True
