"""The hold-out's lists. A new one starts from a pin the corpus lacks. One that is measured is read only in aggregate, so
no command opens its items: a repo worked on becomes corpus."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2])]
import http_corpus as H  # noqa: E402
import lists_store as S  # noqa: E402


def measured(g: dict) -> bool:
    """Every item of the checked sample has a verdict."""
    items = [i for kind in (g.get("checked") or {}).values() for i in kind]
    return bool(items) and all(i.get("ok") is not None for i in items)


def overlap(pins: dict, corpus: dict) -> list[str]:
    """Where a set of pinned repos shares a name or a GitHub repo with the corpus."""
    slugs = {slug.lower(): name for name, (slug, _) in corpus.items()}
    found = []
    for name, (slug, _) in pins.items():
        if name in corpus:
            found.append(f"{name}: a name in the corpus")
        if slug.lower() in slugs:
            found.append(f"{name}: its repo {slug.lower()} is the corpus's {slugs[slug.lower()]}")
    return found


def check_new(name: str, sha: str) -> None:
    """A new list needs its repo pinned in HOLDOUT at this sha, and unknown to the corpus."""
    if name not in H.HOLDOUT:
        raise S.ListError(f"'{name}' is not pinned in HOLDOUT (scripts/http_corpus.py)")
    pinned = H.HOLDOUT[name][1]
    if pinned != sha:
        raise S.ListError(f"'{name}' is pinned at {pinned[:12]}, not {sha[:12]}")
    seen = overlap({name: H.HOLDOUT[name]}, H.CORPUS)
    if seen:
        raise S.ListError(f"'{name}' cannot be a hold-out: " + "; ".join(seen))


def check_open(name: str, g: dict) -> None:
    if measured(g):
        raise S.ListError(f"hold-out list '{name}' is measured, so its items are read only in aggregate; a repo worked on "
                          "becomes corpus: move its list to corpus_expected/ and its pin to CORPUS")
