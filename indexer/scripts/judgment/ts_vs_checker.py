"""The CALLS edges a change gives TS and JS call sites, against the declaration TypeScript's checker gives each site.

   ts_vs_checker.py REPO BEFORE_DIR AFTER_DIR CHECKER.jsonl [--sample N [--seed S]]

BEFORE_DIR and AFTER_DIR hold the micro dry-runs of the two trees (`micro.sh` leaves them in $C/micro), REPO.json.gz in
each. CHECKER.jsonl is `node checks/ts_checker.js --link /corpus/REPO` run in the test image: one row per call, with its
file, line, method and the declarations it resolves to (`outside` for one of a package). Run it offline, on the host.

It prints, for the typed edges the change adds (`receiver-type` and `inherited`, ambiguous or not) and for the by-name
edges it drops, what the checker says about the edge's callee at that site: `agrees`, `checker: another declaration`,
`checker: outside`, `checker: none`, or `no checker site` (the checker has no row for the call). A `.d.ts` that stands for the
JS beside it counts as the same declaration (`agrees (via .d.ts pair)`). A dropped edge is `replaced` when the site keeps an
edge to a method of that name, and `lost` when it keeps none. With --sample, it lists added typed edges where the checker
names another declaration, to read at the source."""
import collections
import gzip
import json
import random
import re
import sys

TS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
TYPED = ("receiver-type", "inherited")
NO_SITE = "no checker site"


def load(directory, repo):
    return json.load(gzip.open(f"{directory}/{repo}.json.gz", "rt"))


def strip_ext(path):
    return re.sub(r"\.[^./]+$", "", path)


def pair(qualified):
    """`x.d:Type.m` is `x:Type.m`: a declaration file stands for the JS beside it."""
    return re.sub(r"\.d:", ":", qualified)


def path_of(node_id):
    """The checker's file key of an id: a symbol's file, or a file's own path, without the extension."""
    if "/sym/" in node_id:
        return node_id.split("/sym/", 1)[1].split(":", 1)[0]
    return strip_ext(node_id.split("/file/", 1)[1])


def qualified(callee_id):
    return callee_id.split("/sym/", 1)[1].split("#", 1)[0]


def method_of(qual):
    return re.split(r"[.:]", qual)[-1]


def checker_sites(path):
    sites = collections.defaultdict(list)
    with open(path) as rows:
        for line in rows:
            row = json.loads(line)
            sites[(strip_ext(row["file"]), row["line"], row["method"])].append(row["declared"])
    return sites


def key(call):
    return (call["caller_id"], call["line"], call["callee_id"])


def in_ts(run):
    """A predicate: the call is made in a TS or JS file."""
    path = {f["id"]: f["path"] for f in run["files"]}
    file_of = {s["id"]: s["file_id"] for s in run["symbols"]}
    return lambda call: path.get(file_of.get(call["caller_id"], call["caller_id"]), "").endswith(TS_SUFFIXES)


def declared_at(call, sites):
    qual = qualified(call["callee_id"])
    found = sites.get((path_of(call["caller_id"]), call["line"], method_of(qual)))
    return qual, (None if found is None else {d for declared in found for d in declared})


def verdict(call, sites):
    qual, declared = declared_at(call, sites)
    if declared is None:
        return NO_SITE
    if qual in declared:
        return "agrees"
    if not declared:
        return "checker: none"
    if declared <= {"outside"}:
        return "checker: outside"
    return "agrees (via .d.ts pair)" if qual in {pair(d) for d in declared} else "checker: another declaration"


def share(counter, *good):
    """(agreeing, with a checker site, percent) over the verdicts that have a checker site."""
    total = sum(n for v, n in counter.items() if v != NO_SITE)
    ok = sum(counter[v] for v in good)
    return ok, total, 100 * ok / max(total, 1)


class Analysis:
    def __init__(self, before, after, sites):
        ts_before, ts_after = in_ts(before), in_ts(after)
        kept = {key(c) for c in after["calls"]}
        had = {key(c) for c in before["calls"]}
        self.added = [c for c in after["calls"] if ts_after(c) and key(c) not in had
                      and c["strategy"].removesuffix("-ambiguous") in TYPED]
        self.dropped = [c for c in before["calls"] if ts_before(c) and key(c) not in kept]
        site_has = {(c["caller_id"], c["line"], method_of(qualified(c["callee_id"]))) for c in after["calls"]}
        self.sites = sites
        self.added_verdicts = collections.Counter(verdict(c, sites) for c in self.added)
        self.dropped_verdicts = collections.Counter(verdict(c, sites) for c in self.dropped)
        self.fate = collections.Counter(
            ("replaced" if (c["caller_id"], c["line"], method_of(qualified(c["callee_id"]))) in site_has else "lost", verdict(c, sites))
            for c in self.dropped)

    def disagreements(self):
        return [c for c in self.added if verdict(c, self.sites) == "checker: another declaration"]


def report(repo, analysis, sample, seed):
    out = []
    out.append(f"{repo} typed edges the change adds: {len(analysis.added)} {dict(analysis.added_verdicts)}")
    out.append(f"{repo} by-name edges the change drops: {len(analysis.dropped)} {dict(analysis.dropped_verdicts)}")
    ok, total, pct = share(analysis.added_verdicts, "agrees", "agrees (via .d.ts pair)")
    out.append(f"  added with a checker site: {total}, agree {ok} ({pct:.1f} %, a .d.ts pair counts as the same declaration)")
    ok, total, pct = share(analysis.dropped_verdicts, "agrees", "agrees (via .d.ts pair)")
    out.append(f"  dropped with a checker site: {total}, the checker agrees with the callee {ok} ({pct:.2f} %)")
    out.append("dropped, by whether the site keeps an edge to a method of that name, and the checker's verdict:")
    out.extend(f"  {n} {fate}: {checker}" for (fate, checker), n in sorted(analysis.fate.items()))
    if sample:
        rows = analysis.disagreements()
        out.append(f"{len(rows)} added typed edges where the checker names another declaration")
        for c in random.Random(seed).sample(rows, min(sample, len(rows))):
            qual, declared = declared_at(c, analysis.sites)
            out.append(f"  {path_of(c['caller_id'])}:{c['line']} [{c['strategy']}] -> {qual}; the checker: {sorted(declared)[:3]}")
    return out


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = dict(zip(argv, argv[1:]))
    if len(args) < 4:
        print(__doc__, file=sys.stderr)
        return 2
    repo, before_dir, after_dir, checker = args[:4]
    analysis = Analysis(load(before_dir, repo), load(after_dir, repo), checker_sites(checker))
    print("\n".join(report(repo, analysis, int(flags.get("--sample", 0)), int(flags.get("--seed", 7)))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
