"""Where the expected lists and the corpus runs are, and how a list is read and written. A list is written back in the
form it was read: keys and items keep their order, because the files have many orders and a tool that sorts turns one
edit into a diff of the whole file."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LISTS = ROOT / "indexer" / "tests" / "corpus_expected"
RUNS = Path(os.environ.get("AIDD_CORPUS_HOME") or Path.home() / ".cache" / "aidd-corpus") / "runs"


class ListError(Exception):
    pass


def dumps(g: dict) -> str:
    return json.dumps(g, indent=1, ensure_ascii=False) + "\n"


def names(directory: Path = LISTS) -> list[str]:
    return sorted(p.stem for p in directory.glob("*.json"))


def load(name: str, directory: Path = LISTS) -> dict:
    path = directory / f"{name}.json"
    if not path.exists():
        raise ListError(f"no expected list '{name}' in {directory}")
    return json.loads(path.read_text())


def save(name: str, g: dict, directory: Path = LISTS) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.json").write_text(dumps(g))


def load_run(label: str, name: str, runs: Path = RUNS) -> dict | None:
    path = runs / label / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None
