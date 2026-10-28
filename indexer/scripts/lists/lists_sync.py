"""A list's checked sample against a corpus run. A checked item is a route the extractor gave at an evidence
(`repo:file:line`), judged by hand. When an extractor change moves it, its verdict no longer holds: the item is dropped
if the run has nothing at that evidence, replaced by the route the run gives there if it has one, and left for the
author if it has several. A replaced item is right when the expected list has the route, and pending otherwise."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2])]
import corpus_metrics as M  # noqa: E402


class SyncError(Exception):
    pass


@dataclass
class Change:
    kind: str
    status: str                  # gone | changed | ambiguous | new
    old: dict | None
    new: dict | None = None


def in_expected(item: dict, g: dict, kind: str) -> bool:
    """The expected list has the route, by the corpus's own matching (a verb of ANY, case-insensitive frameworks)."""
    score = M.score({kind: [item]}, {kind: g.get(kind, [])}, kind)
    return score is not None and not score.false_positives


def _verdict(item: dict, g: dict, kind: str) -> dict:
    return {**item, "ok": True if in_expected(item, g, kind) else None, "category": None}


def _seed(g: dict, name: str, seed: str | None) -> str:
    kept = g.get("checked_seed")
    if seed is not None and kept is not None and str(kept) != seed:
        raise SyncError(f"'{name}' keeps seed {kept}, not {seed}")
    return str(kept) if kept is not None else (seed if seed is not None else "0")


def _moved(item: dict, found: dict, g: dict, kind: str) -> dict:
    route = {"evidence": item["evidence"], "method": found["method"], "path": found["path"],
             "raw": found.get("raw_pattern") or found.get("raw_path")}
    return _verdict(route, g, kind)


def _reconcile_item(g: dict, kind: str, item: dict, here: list[dict]) -> tuple[dict | None, Change | None]:
    if any(x["method"] == item["method"] and x["path"] == item["path"] for x in here):
        return item, None
    if not here:
        return None, Change(kind, "gone", item)
    if len(here) > 1:
        return item, Change(kind, "ambiguous", item)
    moved = _moved(item, here[0], g, kind)
    return moved, Change(kind, "changed", item, moved)


def reconcile(g: dict, run: dict) -> list[Change]:
    """Brings every checked item up to the run; changes the list in memory and says what it did."""
    changes = []
    for kind, items in (g.get("checked") or {}).items():
        at: dict[str, list[dict]] = {}
        for x in run.get(kind, []):
            at.setdefault(x["evidence"], []).append(x)
        kept = []
        for item in items:
            new, change = _reconcile_item(g, kind, item, at.get(item["evidence"], []))
            kept += [new] if new is not None else []
            changes += [change] if change else []
        items[:] = kept
    return changes


def resample(g: dict, run: dict, kind: str, name: str) -> list[Change]:
    """Draws the sample again with the list's seed and size. An item the earlier sample judged keeps its verdict when
    the route is the same; one the expected list has is right; the rest are pending."""
    old = (g.get("checked") or {}).get(kind)
    if not old or g.get("checked_seed") is None:
        raise SyncError(f"'{name}' has no checked {kind} or no checked_seed")
    before = {(i["method"], i["evidence"]): i for i in old}
    drawn = []
    for item in M.sample(run, kind, len(old), g["checked_seed"], name):
        earlier = before.get((item["method"], item["evidence"]))
        if earlier is not None and earlier["path"] == item["path"] and not in_expected(item, g, kind):
            item["ok"], item["category"] = earlier.get("ok"), earlier.get("category")
        else:
            item = _verdict(item, g, kind)
        drawn.append(item)
    g["checked"][kind] = drawn
    key = {(i["method"], i["evidence"], i["path"]) for i in drawn}
    gone = [Change(kind, "gone", i) for i in old if (i["method"], i["evidence"], i["path"]) not in key]
    made = {(i["method"], i["evidence"], i["path"]) for i in old}
    return gone + [Change(kind, "new", None, i) for i in drawn if (i["method"], i["evidence"], i["path"]) not in made]


def draw(g: dict, run: dict, name: str, n: int, seed: str | None = None) -> list[str]:
    """A first sample for each kind the run has and the list has none for: `n` routes drawn with the list's seed, or with
    the one given, which the list then keeps. A route the expected list has is right; the rest are pending."""
    seed = _seed(g, name, seed)
    kinds = [k for k in M.KINDS if run.get(k) and not (g.get("checked") or {}).get(k)]
    if not kinds:
        raise SyncError(f"nothing to draw for '{name}': the run has no routes, or every kind it has is sampled "
                        "(resample draws one again)")
    for kind in kinds:
        g.setdefault("checked", {})[kind] = [_verdict(item, g, kind) for item in M.sample(run, kind, n, seed, name)]
    g.setdefault("checked_seed", seed)
    return kinds
