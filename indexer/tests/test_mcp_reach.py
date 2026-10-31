"""`impact_of`'s walk, against every chain of calls enumerated: the hops are the shortest chain's, `via_ambiguous` says
some chain within the depth has an ambiguous hop, and `via_dispatch` that every one has a dispatch. Without a
dispatch on an acyclic graph, the chains that pass no call twice, which a Cypher `[:CALLS*1..d]` path matches, are all
the chains, so the walk answers what that path did."""

import random

from aidd_indexer.mcp.reach import Hop, Reach, walk

Edge = tuple[str, str, bool, bool]          # caller, callee, ambiguous, dispatch


def _walk(edges: list[Edge], targets: list[str], depth: int) -> dict[str, Reach]:
    def callers_of(ids):
        return [Hop(a, b, "same-module-ambiguous" if amb else "receiver-type", d) for a, b, amb, d in edges if b in ids]
    return walk(callers_of, targets, depth)


def _chains(edges: list[Edge], targets: list[str], depth: int, twice: bool) -> dict[str, Reach]:
    """Every chain of at most `depth` calls from a symbol to a target, a call passed twice only if `twice`."""
    found: dict[str, list[tuple[int, bool, bool]]] = {}

    def follow(start, at, used):
        if used and at in targets:
            found.setdefault(start, []).append(
                (len(used), any(edges[i][2] for i in used), any(edges[i][3] for i in used)))
        for i, (a, b, _, _) in enumerate(edges):
            if a == at and len(used) < depth and (twice or i not in used):
                follow(start, b, used + [i])

    for s in {a for a, *_ in edges} - set(targets):
        follow(s, s, [])
    return {s: Reach(min(n for n, _, _ in c), any(a for _, a, _ in c), all(d for _, _, d in c))
            for s, c in found.items()}


def _graph(rng: random.Random, acyclic: bool, dispatch: bool) -> list[Edge]:
    nodes = [f"n{i}" for i in range(7)]
    edges = set()
    for _ in range(rng.randint(3, 12)):
        a, b = rng.sample(nodes, 2)
        if acyclic and a < b:
            a, b = b, a
        edges.add((a, b, rng.random() < 0.3, dispatch and rng.random() < 0.3))
    return sorted(edges)


def test_without_a_dispatch_on_an_acyclic_graph_the_walk_answers_what_a_cypher_path_did():
    rng = random.Random(7)
    for _ in range(400):
        edges, depth = _graph(rng, acyclic=True, dispatch=False), rng.randint(1, 6)
        assert _walk(edges, ["n0", "n1"], depth) == _chains(edges, ["n0", "n1"], depth, twice=False)


def test_the_walk_answers_what_every_chain_does_with_recursion_and_dispatch():
    rng = random.Random(11)
    for _ in range(400):
        edges, depth = _graph(rng, acyclic=False, dispatch=True), rng.randint(1, 5)
        assert _walk(edges, ["n0"], depth) == _chains(edges, ["n0"], depth, twice=True)


def test_a_dispatch_at_any_hop_reaches_and_a_plain_chain_clears_the_mark():
    edges = [("handler", "service", False, False),
             ("service", "Leaf.save", False, True),     # service calls Base.save(), which Leaf.save may run
             ("job", "Leaf.save", False, False),
             ("cron", "job", False, False), ("cron", "Leaf.save", False, True)]
    out = _walk(edges, ["Leaf.save"], 6)
    assert out == {"service": Reach(1, False, True), "handler": Reach(2, False, True), "job": Reach(1, False, False),
                   "cron": Reach(1, False, False)}
    assert _walk(edges, ["Leaf.save"], 1)["cron"] == Reach(1, False, True)
