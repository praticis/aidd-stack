"""Knowledge service: notes, lifecycle, index block, insights_for, policy_for (fake mirror, no Qdrant)."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

from aidd_indexer.knowledge.insights import Layout
from aidd_indexer.knowledge.service import KnowledgeService
from aidd_indexer.knowledge.vault import KnowledgeError, split_frontmatter


class FakeMirror:
    """Word-overlap similarity instead of embeddings; remembers what was upserted."""

    def __init__(self):
        self.points: dict[str, tuple[str, str, str]] = {}      # note -> (text, topic, project)
        self.client = None

    def similar(self, collection, text, topic, owners, limit=3):
        words = set(re.findall(r"[a-z]+", text.lower()))
        out = []
        for note, (t, tp, proj) in self.points.items():
            if tp == topic and proj in owners:
                other = set(re.findall(r"[a-z]+", t.lower()))
                out.append((len(words & other) / max(1, len(words | other)), note))
        return sorted(out, reverse=True)[:limit]

    def upsert(self, collection, insight):
        from aidd_indexer.knowledge.vectors import document
        m = insight.meta
        self.points[insight.rel] = (document(insight), m["topic"], m["repos"][0] if m["scope"] == "repo" else "shared")


EV = [{"source": "pr-review", "location": "internal/refund/handler.go:42", "link": "https://example.test/pr/48"}]


@pytest.fixture()
def svc(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AIDD_POLICY", raising=False)
    days = iter([f"2026-10-{d:02d}" for d in range(1, 29)])
    return KnowledgeService(tmp_path / "vault", FakeMirror(), "acme", policy_path=str(tmp_path / "none.yaml"),
                            manifest_path=str(tmp_path / "none-atlas.yaml"), threshold=0.6, clock=lambda: next(days))


def record(svc, summary="Refund handler must validate the command before calling the repository", **kw):
    args = dict(repo="orders-api", topic="review", summary=summary,
                what_happened="A refund for a closed account reached the repository unchecked.",
                what_to_do="Run the command validator first; return 422 when it fails.", severity="high", evidence=EV)
    args.update(kw)
    return svc.record_insight(**args)


def test_first_record_creates_note_index_and_point(svc):
    out = record(svc, applies_to={"roles": ["command-handler"]})
    assert out["result"] == "created" and out["status"] == "observed" and out["occurrences"] == 1
    note = svc.layout.root / out["note"]
    assert out["note"] == "acme/knowledge/orders-api/insights/refund-handler-must-validate-the-command-before-calling-the.md"
    meta, body = split_frontmatter(note.read_text())
    assert meta["id"] == "acme/orders-api/refund-handler-must-validate-the-command-before-calling-the"
    assert meta["evidence"][0]["source"] == "pr-review" and meta["evidence"][0]["repo"] == "orders-api"
    assert "## What to do instead\nRun the command validator first" in body
    index = (svc.layout.root / "acme/knowledge/orders-api/orders-api.md").read_text()
    assert "<!-- aidd:knowledge:start -->" in index and "### Review" in index and "observed · 1×" in index
    assert out["index_pages"] == ["acme/knowledge/orders-api/orders-api.md"]
    assert out["note"] in svc.mirror.points


def test_repeats_count_and_become_recurring(svc):
    record(svc)
    out = record(svc, evidence=[{"source": "review", "note": "rejected again"}])
    assert out["result"] == "updated" and out["occurrences"] == 2 and out["status"] == "observed"
    out = record(svc, summary="refund handler must validate the command before calling the repository!")   # same sentence
    assert out["occurrences"] == 3 and out["status"] == "recurring"                   # policy: recurring_after 3
    meta, _ = split_frontmatter((svc.layout.root / out["note"]).read_text())
    assert [e["source"] for e in meta["evidence"]] == ["pr-review", "review", "pr-review"]   # newest first
    assert str(meta["first_seen"]) == "2026-10-01" and str(meta["last_seen"]) == "2026-10-03"
    assert "first_seen: 2026-10-01" in (svc.layout.root / out["note"]).read_text()        # a YAML date, unquoted
    assert ((svc.layout.root / out["note"]).stat().st_mode & 0o777) == 0o644


def test_semantic_match_and_a_different_insight(svc):
    record(svc)
    close = record(svc, summary="Refund handler should validate the command before it calls the repository")
    assert close["result"] == "updated" and close["matched_score"] >= 0.6
    other = record(svc, summary="Statement export duplicates rows when the page size is zero")
    assert other["result"] == "created"
    other_topic = record(svc, topic="security")                                       # same text, other topic
    assert other_topic["result"] == "created"


def test_people_keep_their_edits_and_promotions(svc):
    out = record(svc)
    note = svc.layout.root / out["note"]
    meta, body = split_frontmatter(note.read_text())
    meta["status"], meta["approved_by"] = "accepted", "a reviewer"
    from aidd_indexer.knowledge.vault import join_frontmatter
    note.write_text(join_frontmatter(meta, body.replace("## Notes\n", "## Notes\nDiscussed in the guild.\n")))
    again = record(svc)
    meta, body = split_frontmatter(note.read_text())
    assert again["status"] == "accepted" and meta["approved_by"] == "a reviewer"
    assert "Discussed in the guild." in body
    index = (svc.layout.root / "acme/knowledge/orders-api/orders-api.md").read_text()
    assert "**accepted** · 2×" in index


def test_index_block_only_touches_its_markers(svc):
    page = svc.layout.root / "acme/knowledge/orders-api/orders-api.md"
    page.parent.mkdir(parents=True)
    human = "Decisions we took in the kickoff.\n"
    page.write_text("---\ntype: project-index\nproject: orders-api\n---\n\n# orders-api\n\n"
                    "<!-- aidd:scan:start -->\n## Overview\nscan text\n<!-- aidd:scan:end -->\n\n" + human)
    record(svc)
    text = page.read_text()
    assert text.index("aidd:scan:end") < text.index("aidd:knowledge:start")          # canonical position
    assert human in text and "scan text" in text
    before = text
    record(svc, summary="Statement export duplicates rows when the page size is zero")
    text = page.read_text()
    assert text.count("aidd:knowledge:start") == 1 and human in text and text != before


def test_insights_for_splits_rules_and_context_and_filters(svc):
    a = record(svc, applies_to={"roles": ["command-handler"]})
    b = record(svc, summary="Statement export duplicates rows when the page size is zero", topic="quality",
               severity="medium", applies_to={"files": ["internal/statement/*.go"]})
    record(svc, summary="Never log the full card number in any repo", topic="security", severity="critical", scope="shared")
    note = svc.layout.root / a["note"]
    meta, body = split_frontmatter(note.read_text())
    meta["status"] = "accepted"
    from aidd_indexer.knowledge.vault import join_frontmatter
    note.write_text(join_frontmatter(meta, body))

    everything = svc.insights_for("orders-api")
    assert [i["summary"][:6] for i in everything["rules"]] == ["Refund"]
    assert {i["topic"] for i in everything["context"]} == {"quality", "security"}
    assert everything["context"][0]["severity"] == "critical"                         # worst first
    assert everything["rules"][0]["what_to_do"].startswith("Run the command validator")

    files = svc.insights_for("orders-api", files=["internal/statement/export.go"])
    assert {i["summary"][:9] for i in files["context"]} == {"Statement", "Never log"}   # match + general
    assert files["rules"] == []                                                       # role-specific: not touched
    roles = svc.insights_for("orders-api", roles=["command-handler"])
    assert len(roles["rules"]) == 1
    assert svc.insights_for("billing-api")["context"][0]["scope"] == "shared"         # shared, every repo
    assert svc.insights_for("orders-api", topic="quality")["context"][0]["note"] == b["note"]


def test_shared_insight_shows_in_the_repo_index(svc):
    out = record(svc, summary="Never log the full card number in any repo", topic="security", scope="shared")
    assert out["note"].startswith("acme/knowledge/shared/insights/")
    index = (svc.layout.root / "acme/knowledge/orders-api/orders-api.md").read_text()
    assert "(shared)" in index and "[[acme/knowledge/shared/insights/never-log-the-full-card-number-in-any-repo|" in index


@pytest.mark.parametrize("kw,message", [
    ({"topic": "secruity"}, "did you mean 'security'?"),
    ({"evidence": []}, "evidence is required"),
    ({"evidence": [{"source": "chat"}]}, "evidence source must be one of"),
    ({"evidence": [{"source": "review", "url": "x"}]}, "unknown evidence keys"),
    ({"summary": "x" * 201}, "1–200 characters"),
    ({"severity": "urgent"}, "severity must be one of"),
    ({"what_to_do": " "}, "what_happened and what_to_do are required"),
    ({"repo": "shared"}, "reserved"),
    ({"repo": "../etc"}, "invalid repo name"),
    ({"tenant": ".."}, "invalid tenant name"),
    ({"applies_to": {"paths": ["x"]}}, "applies_to takes"),
    ({"scope": "global"}, "scope is 'repo' or 'shared'"),
])
def test_refusals_say_why(svc, kw, message):
    with pytest.raises(KnowledgeError) as e:
        record(svc, **kw)
    assert message in str(e.value)
    assert not any((svc.layout.root).rglob("insights/*.md"))                           # nothing written


def test_multi_tenant_needs_the_tenant(tmp_path: Path):
    s = KnowledgeService(tmp_path, FakeMirror(), None, policy_path=str(tmp_path / "none.yaml"))
    with pytest.raises(KnowledgeError, match="pass `tenant`"):
        s.insights_for("orders-api")
    assert s.insights_for("orders-api", tenant="globex")["tenant"] == "globex"


def test_policy_for_and_custom_topics(tmp_path: Path):
    pol = tmp_path / "policy.yaml"
    pol.write_text("tenants:\n  acme:\n    knowledge: {topics: [performance]}\n    coverage: {min: 85}\n")
    s = KnowledgeService(tmp_path / "v", FakeMirror(), "acme", policy_path=str(pol), manifest_path=str(tmp_path / "x.yaml"))
    p = s.policy_for("orders-api")
    assert p["policy"]["coverage"]["min"] == 85 and p["origin"]["coverage.min"] == "tenant acme"
    out = record(s, topic="performance")
    assert out["result"] == "created"
    assert "### Performance" in (s.layout.root / "acme/knowledge/orders-api/orders-api.md").read_text()


def test_mcp_tools(svc):
    from aidd_indexer.knowledge.server import build_server
    srv = build_server(service=svc)
    names = {t.name for t in asyncio.run(srv.list_tools())}
    assert {"policy_for", "insights_for", "record_insight"} <= names
    res = asyncio.run(srv.call_tool("record_insight", {
        "repo": "orders-api", "topic": "review", "summary": "Handlers validate commands first",
        "what_happened": "x", "what_to_do": "y", "severity": "low", "evidence": [{"source": "session"}]}))
    content = res[0] if isinstance(res, tuple) else res
    assert json.loads(content[0].text)["result"] == "created"
