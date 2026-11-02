"""`record_insight`'s refusals in the order it checks them, and its answers when the mirror fails or the agent must
decide (fake mirror, no Qdrant)."""
from __future__ import annotations

from pathlib import Path

import pytest

from aidd_indexer.knowledge.service import KnowledgeService
from aidd_indexer.knowledge.vault import KnowledgeError
from test_knowledge import FakeMirror, record, svc  # noqa: F401  (the fixture)

TOPICS = "architecture, review, quality, security, incident, decision, business"


def refusal(s, **kw) -> str:
    with pytest.raises(KnowledgeError) as e:
        record(s, **kw)
    return str(e.value)


@pytest.mark.parametrize("kw,message", [
    ({"topic": "secruity", "summary": "x" * 201},
     f"unknown topic 'secruity' — did you mean 'security'? (topics: {TOPICS}; extend them in policy.yaml knowledge.topics)"),
    ({"topic": "zzz"}, f"unknown topic 'zzz' (topics: {TOPICS}; extend them in policy.yaml knowledge.topics)"),
    ({"summary": "   \n ", "severity": "urgent"},
     "summary is one sentence of 1–200 characters: the problem and what to do instead"),
    ({"severity": "urgent", "what_to_do": " "}, "severity must be one of low, medium, high, critical"),
    ({"what_happened": "", "scope": "global"},
     "what_happened and what_to_do are required (the case that triggered it, and the rule)"),
    ({"what_happened": None}, "what_happened and what_to_do are required (the case that triggered it, and the rule)"),
    ({"scope": "global", "evidence": []}, "scope is 'repo' or 'shared'"),
])
def test_the_first_defect_is_the_one_named(svc, kw, message):
    assert refusal(svc, **kw) == message
    assert not any(svc.layout.root.rglob("insights/*.md"))


def test_without_qdrant_the_arguments_are_still_checked_first(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AIDD_POLICY", raising=False)
    s = KnowledgeService(tmp_path / "v", None, "acme", policy_path=str(tmp_path / "none.yaml"),
                         manifest_path=str(tmp_path / "none-atlas.yaml"))
    assert "evidence is required" in refusal(s, evidence=[])
    assert refusal(s) == "Qdrant is not configured for the knowledge service — nothing recorded"


def test_the_summary_is_kept_on_one_line(svc):
    out = record(svc, summary="  Refund handler\n   must validate   the command  ")
    assert svc.layout.load(svc.layout.root / out["note"]).meta["summary"] == "Refund handler must validate the command"


class Broken(FakeMirror):
    def __init__(self, fails: str):
        super().__init__()
        self.fails = fails

    def similar(self, *a, **kw):
        if self.fails == "similar":
            raise RuntimeError("down")
        return super().similar(*a, **kw)

    def upsert(self, collection, insight):
        if self.fails == "upsert":
            raise RuntimeError("x")
        return super().upsert(collection, insight)


def test_a_failing_mirror_says_what_was_written(svc):
    svc.mirror = Broken("upsert")
    said = refusal(svc)
    (note,) = svc.layout.root.rglob("insights/*.md")
    rel = svc.layout.rel(note)
    assert said == (f"note created at {rel}, but the Qdrant mirror failed (RuntimeError: x); "
                    "semantic search will miss it until it is recorded again")
    assert refusal(svc) == said.replace("note created", "note updated")

    svc.mirror = Broken("similar")
    assert refusal(svc, summary="Another sentence entirely about a different thing") == (
        "Qdrant unavailable (RuntimeError: down) — not recorded, to avoid a duplicate")


def test_the_answers(svc):
    first = record(svc)
    assert set(first) == {"result", "id", "note", "status", "occurrences", "index_pages"}
    assert (first["result"], first["status"], first["occurrences"]) == ("created", "observed", 1)
    again = record(svc)
    assert {k: again[k] for k in ("result", "id", "occurrences", "matched_score")} == {
        "result": "updated", "id": first["id"], "occurrences": 2, "matched_score": 1.0}
    assert "matched" not in again
    same = record(svc, summary="Other words", same_as=first["id"])
    assert same["matched"] == "same_as" and "matched_score" not in same


def test_needs_decision_is_the_whole_answer(svc):
    first = record(svc, applies_to={"symbols": ["Orders.Refund.CreateRefundHandler"]})
    out = record(svc, summary="Totally unrelated wording about something",
                 applies_to={"symbols": ["Orders.Refund.CreateRefundHandler"]})
    assert set(out) == {"result", "recorded", "candidates", "next"}
    assert (out["result"], out["recorded"]) == ("needs_decision", False)
    (c,) = out["candidates"]
    assert (c["id"], c["why"]) == (first["id"], "same symbols/files") and "score" in c
    assert out["next"] == (
        "Nothing was written. Read the candidates: if one is the same insight (said in other words or another "
        "language), call record_insight again with the same arguments and same_as=<its id> — it counts one more "
        "occurrence. If it is a different insight, call again with new=true.")
