"""Every change between main's expected lists and HEAD's, classified.

usage: expected_lists_diff.py MAIN_DIR HEAD_DIR RUN_DIR
  expected pairs removed or added; categories cleared (and whether RUN finds the pair) or newly set;
  checked verdicts flipped, checked items dropped or added.
Needs corpus_metrics and aidd_indexer importable: in the indexer image, PYTHONPATH=/src:/src/scripts."""
import json
import sys
from pathlib import Path

from corpus_metrics import KINDS, _check_id, item_key, score

main_dir, head_dir, run_dir = (Path(a) for a in sys.argv[1:4])
totals = {}


def bump(k, n=1):
    totals[k] = totals.get(k, 0) + n


for hp in sorted(head_dir.glob("*.json")):
    mp = main_dir / hp.name
    h = json.loads(hp.read_text())
    m = json.loads(mp.read_text()) if mp.exists() else None
    if m == h:
        continue
    repo = hp.stem
    if m is None:
        print(f"== {repo}: new expected list")
        bump("new expected lists")
        continue
    run_path = run_dir / f"{repo}.json"
    run = json.loads(run_path.read_text()) if run_path.exists() else {}
    lines = []
    for kind in KINDS:
        me = {item_key(i): i for i in m.get(kind, []) or []}
        he = {item_key(i): i for i in h.get(kind, []) or []}
        if (kind in m) != (kind in h):
            lines.append(f"  {kind}: kind {'added' if kind in h else 'REMOVED'}")
        sc = score(run, h, kind) if kind in h else None
        fn = set(sc.false_negatives) if sc else set()
        for k in sorted(set(me) - set(he)):
            lines.append(f"  {kind}: expected REMOVED {k} (main category {me[k].get('category')})")
            bump(f"{kind} expected removed")
        for k in sorted(set(he) - set(me)):
            lines.append(f"  {kind}: expected added {k} category={he[k].get('category')} found={k not in fn}")
            bump(f"{kind} expected added")
        for k in sorted(set(me) & set(he)):
            a, b = me[k].get("category"), he[k].get("category")
            if a and not b:
                bump(f"{kind} category cleared")
                if k in fn:
                    lines.append(f"  {kind}: category cleared {a} but STILL MISSED {k}")
                    bump(f"{kind} cleared but missed")
            elif b and not a:
                lines.append(f"  {kind}: category NEWLY SET {b} on {k} found={k not in fn}")
                bump(f"{kind} category newly set")
            elif a != b:
                lines.append(f"  {kind}: category changed {a} -> {b} on {k}")
                bump(f"{kind} category changed")
        mc = {_check_id(i): i for i in (m.get("checked") or {}).get(kind, []) or []}
        hc = {_check_id(i): i for i in (h.get("checked") or {}).get(kind, []) or []}
        for k in sorted(set(mc) & set(hc)):
            a, b = mc[k].get("ok"), hc[k].get("ok")
            if a is True and b is False:
                lines.append(f"  {kind}: checked FLIPPED ok->wrong {k} ({hc[k].get('category')})")
                bump(f"{kind} checked ok->wrong")
            elif a is False and b is True:
                bump(f"{kind} checked wrong->ok")
            elif a != b:
                lines.append(f"  {kind}: checked verdict {a} -> {b} {k}")
        for k in sorted(set(mc) - set(hc)):
            lines.append(f"  {kind}: checked dropped {k} ok={mc[k].get('ok')}")
            bump(f"{kind} checked dropped (ok={mc[k].get('ok')})")
        for k in sorted(set(hc) - set(mc)):
            lines.append(f"  {kind}: checked added {k} ok={hc[k].get('ok')}")
            bump(f"{kind} checked added (ok={hc[k].get('ok')})")
    other = sorted(x for x in set(m) | set(h) if x not in KINDS and x != "checked" and m.get(x) != h.get(x))
    print(f"== {repo}: other fields changed: {other}")
    for ln in lines:
        print(ln)

print("\nTOTALS")
for k in sorted(totals):
    print(f"  {k}: {totals[k]}")
