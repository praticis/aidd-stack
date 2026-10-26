"""The sites whose edges changed between two runs, by class (an extension added where there was nothing, one in place
of an `inherited` edge, one in place of a typed edge, a name match of the one extension of any value), with seeded
samples and the source line of each.   ext_judge.py BEFORE AFTER REPOS_DIR N SEED REPO..."""
import collections
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
from edges_lib import edges, load  # noqa: E402

THIS = re.compile(r"\(\s*(\[[^\]]*\]\s*)*this\s")
before, after, repos, n, seed = sys.argv[1], sys.argv[2], Path(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
by_class = collections.defaultdict(list)
for repo in sys.argv[6:]:
    b, a = load(before, repo), load(after, repo)
    ext = {s["qualified_name"] for s in a["symbols"]
           if s.get("kind") == "method" and (THIS.search(s.get("signature") or "") or " static " in f" {s.get('signature') or ''} ")}
    eb, ea = edges(b), edges(a)
    # sorted: a set's order changes from one process to the next, and the seeded sample is drawn in this order
    for site in sorted(ea.keys() | eb.keys()):
        was, now = eb.get(site, set()), ea.get(site, set())
        if was == now:
            continue
        new = now - was
        gained = {(c, s) for c, s in new if c in ext}
        if not gained:
            cls = "other: " + ("removed only" if not new else "added non-extension")
        else:
            strat = "name" if all(s == "unique-name" for _, s in gained) else "typed"
            prev = ("nothing" if not was else "inherited" if all(s.startswith("inherited") for _, s in was)
                    else "typed" if any(s.startswith("receiver-type") for _, s in was) else "name")
            cls = f"extension {strat}, was {prev}"
        by_class[cls].append((repo, site, sorted(was), sorted(now)))
rnd = random.Random(seed)
for cls, rows in sorted(by_class.items(), key=lambda kv: -len(kv[1])):
    print(f"== {cls}: {len(rows)} sites, {dict(collections.Counter(r[0] for r in rows).most_common())}")
    for repo, (f, line), was, now in rnd.sample(rows, min(n, len(rows))):
        src = (repos / repo / f).read_text(errors="replace").splitlines()[line - 1].strip()[:150]
        short = lambda es: [(c.split(".")[-2] + "." + c.split(".")[-1], s) for c, s in es][:3]
        print(f"  {repo} {f}:{line}\n      {src}\n      was {short(was)}\n      now {short(now)}")
