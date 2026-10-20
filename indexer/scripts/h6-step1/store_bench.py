"""H6 step 2: where the per-file cache lives. The entries of a real cache (one file each, as the prototype wrote them)
are written and read again by three stores, on a given directory:

- files: one file per entry, through a temporary file and a rename (the prototype's);
- sqlite: one database, one writer, one transaction per run;
- pack: one file per snapshot, holding every entry the run used, rewritten by each run.

Three scenarios: a cold run fills the store; a warm run reads every entry; a push reads every entry and writes the 1 %
that changed. Runs in the indexer image:

    python store_bench.py /cache-entries /target --rounds 3
"""

import argparse
import os
import pickle
import shutil
import sqlite3
import statistics
import sys
import time
from pathlib import Path


def entries(root: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in root.rglob("*") if p.is_file() and not p.name.startswith(".")}


class Files:
    def __init__(self, d: Path) -> None:
        self.d = d

    def write(self, items: dict) -> None:
        for k, v in items.items():
            p = self.d / k[:2] / k
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(f".{k}.{os.getpid()}")
            tmp.write_bytes(v)
            os.replace(tmp, p)

    def read(self, keys: list) -> int:
        return sum(len((self.d / k[:2] / k).read_bytes()) for k in keys)


class Sqlite:
    def __init__(self, d: Path) -> None:
        d.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(d / "cache.db")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS e (k TEXT PRIMARY KEY, v BLOB) WITHOUT ROWID")

    def write(self, items: dict) -> None:
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO e VALUES (?, ?)", items.items())

    def read(self, keys: list) -> int:
        q = self.db.execute
        return sum(len(q("SELECT v FROM e WHERE k = ?", (k,)).fetchone()[0]) for k in keys)


class Pack:
    def __init__(self, d: Path) -> None:
        d.mkdir(parents=True, exist_ok=True)
        self.p = d / "snapshot.pack"
        self.mem: dict = {}

    def write(self, items: dict) -> None:
        self.mem.update(items)
        tmp = self.p.with_suffix(f".{os.getpid()}")
        tmp.write_bytes(pickle.dumps(self.mem, protocol=5))
        os.replace(tmp, self.p)

    def read(self, keys: list) -> int:
        self.mem = pickle.loads(self.p.read_bytes())
        return sum(len(self.mem[k]) for k in keys)


def timed(fn, *a) -> float:
    t = time.perf_counter()
    fn(*a)
    return time.perf_counter() - t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("target")
    ap.add_argument("--rounds", type=int, default=3)
    a = ap.parse_args()
    items = entries(Path(a.source))
    keys = sorted(items)
    changed = {k[::-1]: items[k] for k in keys[:: 100]}
    print(f"{len(items)} entries, {sum(map(len, items.values())) / 2**20:.1f} MiB; a push writes {len(changed)}")
    for name, cls in (("files", Files), ("sqlite", Sqlite), ("pack", Pack)):
        fill, warm, push = [], [], []
        for r in range(a.rounds):
            d = Path(a.target) / f"{name}-{r}"
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True)
            fill.append(timed(cls(d).write, items))
            warm.append(timed(cls(d).read, keys))
            s = cls(d)
            push.append(timed(lambda: (s.read(keys), s.write(changed))))
            shutil.rmtree(d)
        f = lambda xs: f"{statistics.median(xs):6.2f} ({min(xs):.2f}–{max(xs):.2f})"
        print(f"{name:7} fill {f(fill)}  warm {f(warm)}  push {f(push)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
