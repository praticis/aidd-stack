"""Among the call sites whose edges changed between two dry-runs, the edges to an extension method of the repo that
went away, and what the site has now (typed, inherited, nothing).   ext_loss.py BEFORE AFTER REPO..."""
import collections
import sys

sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
from edges_lib import edges, load  # noqa: E402

before, after = sys.argv[1], sys.argv[2]
total = collections.Counter()
for repo in sys.argv[3:]:
    b, a = load(before, repo), load(after, repo)
    ext = {s["qualified_name"] for s in b["symbols"] + a["symbols"]
           if s.get("kind") == "method" and "(this " in (s.get("signature") or "")}
    eb, ea = edges(b), edges(a)
    lost = collections.Counter()
    for site in eb.keys() | ea.keys():
        was, now = eb.get(site, set()), ea.get(site, set())
        gone = {c for c, _ in was - now if c in ext} - {c for c, _ in now}
        if gone:
            after_kind = "nothing" if not now else "inherited" if all(s == "inherited" for _, s in now) else \
                "typed" if any(s.startswith("receiver-type") for _, s in now) else "name"
            lost[after_kind] += 1
    total.update(lost)
    print(f"{repo}: extension-method sites lost {sum(lost.values())} {dict(lost)}")
print("all:", dict(total), sum(total.values()))
