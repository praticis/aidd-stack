"""Per configuration of a bench directory's logs: the median wall time with its range, the time after the
extraction (the resolver and the output), the parent's garbage collection, the peak, and the map's counters.
   aggregate.py BENCH_DIR"""

from __future__ import annotations

import re
import statistics as st
import sys
from pathlib import Path

NUM = r"([\d.]+)"


def _row(text: str) -> dict | None:
    wall, disc = re.search(rf"wall={NUM}", text), re.search(rf"^\[discover\].*\({NUM}s\)", text, re.M)
    ext, http = re.search(rf"^\[extract\].*\({NUM}s\)", text, re.M), re.search(rf"^\[http\].*\({NUM}s\)", text, re.M)
    if not (wall and disc and ext):
        return None
    row = {k: float(v) for k, v in re.findall(rf"(\w+)={NUM}", text.split("[pipeline]", 1)[-1].split("\n", 1)[0])}
    row.update(wall=float(wall[1]), peak=int(re.search(r"peak=(\d+)", text)[1]) / 2**20,
               post=float(wall[1]) - float(disc[1]) - float(ext[1]) - (float(http[1]) if http else 0.0))
    gc = re.search(rf"\[gc\] seconds={NUM}", text)
    if gc:
        row["gc"] = float(gc[1])
    return row


def main(bench: Path) -> None:
    rows: dict[str, list] = {}
    for log in sorted(bench.glob("*.log")):
        row = _row(log.read_text())
        if row is not None:
            rows.setdefault(re.sub(r"-\d+$", "", log.stem), []).append(row)
    for name, rs in rows.items():
        walls = [r["wall"] for r in rs]
        line = f"{name:22} n={len(rs)} wall={st.median(walls):6.1f} ({min(walls):.1f}-{max(walls):.1f})"
        for key in ("post", "gc", "peak", "map1", "map2", "map1_cpu", "map2_cpu"):
            if all(key in r for r in rs):
                line += f" {key}={st.median(r[key] for r in rs):.1f}"
        for key in ("scanned_early", "early_invalid", "split_files"):
            if key in rs[0]:
                line += f" {key}={rs[0][key]:.0f}"
        print(line)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
