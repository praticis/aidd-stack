"""Edits to an expected list: a new list, an item, a miss category, a field, and the verdicts on its checked sample.
Pure functions over the list as a dict; the command reads and writes the file."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2])]
import corpus_metrics as M  # noqa: E402


class VerdictError(Exception):
    pass


def new_list(sha: str, spec: dict | None = None) -> dict:
    """A list with no items, or the routes an OpenAPI dump (`corpus_metrics.py from-openapi`) declares."""
    if not spec:
        return {"sha": sha, "endpoints": []}
    scope = {"scope": spec["scope"]} if "scope" in spec else {}
    return {"source": "openapi", "sha": sha, "spec": spec.get("spec", []), **scope, "endpoints": spec["endpoints"]}


def _order(item: dict) -> tuple[str, str]:
    return item["path"], item["method"]


def add_item(g: dict, kind: str, method: str, path: str, category: str | None = None) -> bool:
    """Adds the item to a list sorted by (path, method) in its place, and to any other at the end."""
    items = g.setdefault(kind, [])
    if any(i["method"] == method and i["path"] == path for i in items):
        return False
    new = {"method": method, "path": path, **({"category": category} if category else {})}
    if items == sorted(items, key=_order):
        items.insert(next((n for n, i in enumerate(items) if _order(i) > _order(new)), len(items)), new)
    else:
        items.append(new)
    return True


def set_category(g: dict, kind: str, category: str, pattern: str, method: str | None = None) -> int:
    """The category (why the extractor misses the item) of every item whose path matches; `-` clears it."""
    rx, count = re.compile(pattern), 0
    for item in g.get(kind, []):
        if rx.search(item["path"]) and (method is None or item["method"] == method):
            if category == "-":
                item.pop("category", None)
            else:
                item["category"] = category
            count += 1
    return count


def set_fields(g: dict, pairs: list[str]) -> None:
    for pair in pairs:
        key, _, value = pair.partition("=")
        g[key] = json.loads(value)


def found_with_category(g: dict, run: dict) -> list[tuple[str, dict]]:
    """The items a run now finds that still carry a category: why they were missed no longer holds."""
    found = []
    for kind in M.KINDS:
        score = M.score(run, g, kind)
        if score is not None:
            missed = set(score.false_negatives)
            found += [(kind, i) for i in g[kind] if i.get("category") and M.item_key(i) not in missed]
    return found


def pending(g: dict) -> list[tuple[str, int, dict]]:
    """The checked items with no verdict yet: kind, position in its kind, item."""
    return [(kind, n, i) for kind, items in (g.get("checked") or {}).items()
            for n, i in enumerate(items) if i.get("ok") is None]


def parse_verdict(text: str) -> tuple[bool, str | None]:
    ok, _, category = text.partition(":")
    if ok not in ("ok", "wrong"):
        raise VerdictError(f"'{text}' is not a verdict: ok, wrong or wrong:CATEGORY")
    return ok == "ok", category or None


def judge(g: dict, kind: str, default: str, overrides: dict[int, str]) -> int:
    """`default` (`-` for none) goes to the pending items of the kind, each position in `overrides` to its own verdict.
    A verdict never replaces another."""
    items = (g.get("checked") or {}).get(kind) or []
    base = None if default == "-" else parse_verdict(default)
    chosen = {n: parse_verdict(v) for n, v in overrides.items()}
    for n in chosen:
        if n >= len(items):
            raise VerdictError(f"no checked item {n} in {kind}")
        if items[n].get("ok") is not None:
            raise VerdictError(f"item {n} of {kind} is already judged")
    count = 0
    for n, item in enumerate(items):
        verdict = chosen.get(n) or (base if item.get("ok") is None else None)
        if verdict:
            item["ok"], item["category"] = verdict
            count += 1
    return count
