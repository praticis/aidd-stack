"""main's extractor against HEAD's, both scored by today's gabaritos.

usage: a4_compare.py MAIN_RUN HEAD_RUN GABARITO_DIR [--holdout]
  per repo and kind: list P/R on both sides (a drop is reported); gabarito pairs main finds and HEAD misses;
  checked items judged right that main's run has and HEAD's lacks; checked items judged wrong that only HEAD has."""
import json
import sys
from pathlib import Path

from corpus_metrics import KINDS, _check_id, item_key, score

main_dir, head_dir, gab_dir = (Path(a) for a in sys.argv[1:4])
if "--holdout" in sys.argv:
    gab_dir = gab_dir / "holdout"
problems = 0


def pct(x):
    return "—" if x is None else f"{100 * x:.1f}%"


for gp in sorted(gab_dir.glob("*.json")):
    repo = gp.stem
    mp, hp = main_dir / f"{repo}.json", head_dir / f"{repo}.json"
    if not (mp.exists() and hp.exists()):
        print(f"{repo}: missing run (main {mp.exists()}, head {hp.exists()})")
        problems += 1
        continue
    gab = json.loads(gp.read_text())
    m, h = json.loads(mp.read_text()), json.loads(hp.read_text())
    out = []
    for kind in KINDS:
        sm, sh = score(m, gab, kind), score(h, gab, kind)
        if sm is not None:
            drop = (sh.recall or 0) < (sm.recall or 0) or (sh.precision or 0) < (sm.precision or 0)
            out.append(f"  {kind}: {'DROP ' if drop else ''}P {pct(sm.precision)} -> {pct(sh.precision)}, "
                       f"R {pct(sm.recall)} -> {pct(sh.recall)}")
            found_by_main = {item_key(i) for i in gab[kind]} - set(sm.false_negatives)
            lost = sorted(found_by_main & set(sh.false_negatives))
            for k in lost:
                out.append(f"  {kind}: LOST pair {k}")
            problems += len(lost) + int(drop)
        checked = (gab.get("checked") or {}).get(kind) or []
        m_ids = {_check_id(x) for x in m.get(kind, [])}
        h_ids = {_check_id(x) for x in h.get(kind, [])}
        for c in checked:
            cid = _check_id(c)
            if c.get("ok") is True and cid in m_ids and cid not in h_ids:
                out.append(f"  {kind}: LOST checked-right item {cid}")
                problems += 1
            if c.get("ok") is False and cid in h_ids and cid not in m_ids:
                out.append(f"  {kind}: new wrong item (only HEAD) {cid} category={c.get('category')}")
    print(f"{repo}:")
    for ln in out:
        print(ln)
print(f"\nproblems: {problems}")
