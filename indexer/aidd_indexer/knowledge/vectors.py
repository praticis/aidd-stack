"""Embeddings and the Qdrant mirror of insights.

The mirror has to be readable by `mcp-server-qdrant` (the `qdrant-find` the skills call): same
collection per tenant, same named vector (`fast-<model>`), same model, payload
`{"document", "metadata"}`. A different model would make the two sets invisible to each other.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Protocol

from .insights import Insight

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


def vector_name(model: str) -> str:
    """The name mcp-server-qdrant gives the vector (its FastEmbed provider)."""
    return f"fast-{model.split('/')[-1].lower()}"


class Embedder(Protocol):
    model: str
    size: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedder:
    """Passage embeddings with FastEmbed — what mcp-server-qdrant stores with. The model is baked into
    the image (FASTEMBED_CACHE_PATH), so nothing is downloaded at runtime."""

    def __init__(self, model: str | None = None):
        from fastembed import TextEmbedding
        self.model = model or os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)
        self._m = TextEmbedding(self.model, cache_dir=os.getenv("FASTEMBED_CACHE_PATH") or None)
        self.size = len(self.embed(["probe"])[0])

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in v] for v in self._m.passage_embed(texts)]


def document(insight: Insight) -> str:
    """What is embedded and stored: the summary and the rule, read back from the note (people may
    have edited it — the vault wins)."""
    return f"{insight.meta.get('summary', '')}\n\n{insight.section('What to do instead')}".strip()


def point_id(insight_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"aidd-insight:{insight_id}"))


class Mirror:
    def __init__(self, client: Any, embedder: Embedder):
        self.client, self.embedder = client, embedder
        self.vector = vector_name(embedder.model)

    def ensure(self, collection: str) -> None:
        from qdrant_client import models
        if self.client.collection_exists(collection):
            return
        self.client.create_collection(collection, vectors_config={
            self.vector: models.VectorParams(size=self.embedder.size, distance=models.Distance.COSINE)})

    def similar(self, collection: str, text: str, topic: str, owners: list[str], limit: int = 3) -> list[tuple[float, str]]:
        """(score, note path) of the insights closest to `text` with the same topic, among `owners`
        (`metadata.project`: the repo and/or 'shared')."""
        from qdrant_client import models
        if not self.client.collection_exists(collection):
            return []
        flt = models.Filter(must=[
            models.FieldCondition(key="metadata.type", match=models.MatchValue(value="insight")),
            models.FieldCondition(key="metadata.topic", match=models.MatchValue(value=topic)),
            models.FieldCondition(key="metadata.project", match=models.MatchAny(any=owners)),
        ])
        res = self.client.query_points(collection, query=self.embedder.embed([text])[0], using=self.vector,
                                       query_filter=flt, limit=limit, with_payload=True)
        return [(float(p.score), str((p.payload or {}).get("metadata", {}).get("note", ""))) for p in res.points]

    def upsert(self, collection: str, insight: Insight) -> None:
        from qdrant_client import models
        m = insight.meta
        text = document(insight)
        self.ensure(collection)
        self.client.upsert(collection, points=[models.PointStruct(
            id=point_id(str(m["id"])),
            vector={self.vector: self.embedder.embed([text])[0]},
            payload={"document": text, "metadata": {
                "type": "insight", "project": m["repos"][0] if m.get("scope") == "repo" else "shared",
                "topic": m.get("topic"), "status": insight.status, "severity": m.get("severity"),
                "note": insight.rel, "contract": m.get("contract")}},
        )])

    def delete(self, collection: str, insight_id: str) -> None:
        from qdrant_client import models
        if self.client.collection_exists(collection):
            self.client.delete(collection, points_selector=models.PointIdsList(points=[point_id(insight_id)]))
