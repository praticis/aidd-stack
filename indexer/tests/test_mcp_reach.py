"""`impact_of`'s walk, against every chain of calls enumerated: the hops are the shortest chain's, and `via_ambiguous`
and `via_dispatch` say that every chain within the depth has an ambiguous hop, or a dispatch. A chain without the mark
that passes a call twice holds one shorter that does not, so the chains a Cypher `[:CALLS*1..d]` path matches, which
pass no call twice, give the same answers, recursion or not."""

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
    return {s: Reach(min(n for n, _, _ in c), all(a for _, a, _ in c), all(d for _, _, d in c))
            for s, c in found.items()}


def _graph(rng: random.Random) -> list[Edge]:
    nodes = [f"n{i}" for i in range(7)]
    edges = set()
    for _ in range(rng.randint(3, 12)):
        a, b = rng.choice(nodes), rng.choice(nodes)
        edges.add((a, b, rng.random() < 0.3, rng.random() < 0.3))
    return sorted(edges)


def test_the_walk_answers_what_every_chain_does_and_what_a_cypher_path_did():
    rng = random.Random(11)
    for _ in range(600):
        edges, depth, targets = _graph(rng), rng.randint(1, 5), rng.sample(["n0", "n1", "n2"], rng.randint(1, 2))
        assert _walk(edges, targets, depth) == _chains(edges, targets, depth, twice=True) \
            == _chains(edges, targets, depth, twice=False)


def test_a_chain_resolved_by_name_marks_a_caller_only_if_no_other_reaches_it():
    edges = [("x", "t", True, False),                   # x calls t, resolved by name among several
             ("x", "y", False, False), ("y", "t", False, False),
             ("z", "y", True, False),
             ("r", "r", True, False), ("r", "t", False, False)]
    out = _walk(edges, ["t"], 6)
    assert out == {"x": Reach(1, False, False), "y": Reach(1, False, False), "z": Reach(2, True, False),
                   "r": Reach(1, False, False)}
    assert _walk(edges, ["t"], 1)["x"] == Reach(1, True, False)


def test_a_dispatch_at_any_hop_reaches_and_a_plain_chain_clears_the_mark():
    edges = [("handler", "service", False, False),
             ("service", "Leaf.save", False, True),     # service calls Base.save(), which Leaf.save may run
             ("job", "Leaf.save", False, False),
             ("cron", "job", False, False), ("cron", "Leaf.save", False, True)]
    out = _walk(edges, ["Leaf.save"], 6)
    assert out == {"service": Reach(1, False, True), "handler": Reach(2, False, True), "job": Reach(1, False, False),
                   "cron": Reach(1, False, False)}
    assert _walk(edges, ["Leaf.save"], 1)["cron"] == Reach(1, False, True)
