"""The CALLS edges a change gives TS and JS call sites, against the declaration TypeScript's checker gives each site.

   ts_vs_checker.py REPO BEFORE_DIR AFTER_DIR CHECKER.jsonl [--sample N [--seed S]] [--min-keyed PCT] [--strict]

BEFORE_DIR and AFTER_DIR hold the micro dry-runs of the two trees (`micro.sh` leaves them in $C/micro), REPO.json.gz in
each. CHECKER.jsonl is `node checks/ts_checker.js --link /corpus/REPO` run in the test image: one row per call, with its
file, line, method and the declarations it resolves to (`outside` for one of a package). Run it offline, on the host.

It prints, for the typed edges the change adds (`receiver-type` and `inherited`, ambiguous or not) and for the by-name
edges it drops, what the checker says about the edge's callee at that site: `agrees`, `checker: another declaration`,
`checker: outside`, `checker: none`, or `no checker site` (the checker has no row for the call). A `.d.ts` that stands for the
JS beside it counts as the same declaration (`agrees (via .d.ts pair)`), and an edge to the type that owns a member with no
symbol, which the edge's method names, agrees with the checker's declaration of that member (`agrees (owner of the member)`).
An edge to what runs where the checker names the member of a declaration file is `checker: a declaration file's member`:
neither agreement nor contradiction. A dropped edge is `replaced` when the site keeps an edge to a method of that name, and
`lost` when it keeps none. With --sample, it lists added typed edges where the checker names another declaration, to read
at the source.

Each percentage is over the sites the checker has a row for, and the line says how many of the edges that is: a share
read without its denominator is what hid 11,145 of one repository's 15,092 edges when the two sides were keyed
differently. One more line says how many of the TS calls of the two runs are in a file the checker has rows for: with
the keys right it is most of them (97.8 % in the corpus's largest TS repository), with a path compared with its
extension to one without it, none. Below --min-keyed (a percent, 50 by default) it prints a WARNING, and with --strict
it ends in 1. Without a warning it ends in 0, and in 2 when its arguments are wrong."""
import argparse
import collections
import gzip
import json
import random
import re
import sys

TS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
TYPED = ("receiver-type", "inherited")
NO_SITE = "no checker site"
OWNER = "agrees (owner of the member)"
DECLARATION_FILE = "checker: a declaration file's member"
AGREE = ("agrees", "agrees (via .d.ts pair)", OWNER)


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


def called(call):
    """The method a call site names: what the edge records, or, when it records none, the callee's own name. An edge to the
    type that owns a member with no symbol has the type's name as callee, so the callee alone would key it by the wrong
    method and the checker would seem to have no row for it."""
    return call.get("method") or method_of(qualified(call["callee_id"]))


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
    found = sites.get((path_of(call["caller_id"]), call["line"], called(call)))
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
    return by_member(qual, declared - {"outside"}, called(call))


def by_member(qual, inside, method):
    """What an edge is to the declarations of the repo the checker names, when none is the callee itself."""
    if qual in {pair(d) for d in inside}:
        return "agrees (via .d.ts pair)"
    if any(d.endswith("." + method) and pair(d.rsplit(".", 1)[0]) == pair(qual) for d in inside):
        return OWNER
    if all(d.split(":", 1)[0].endswith(".d") for d in inside):
        return DECLARATION_FILE
    return "checker: another declaration"


def share(counter, *good):
    """(agreeing, with a checker site, percent) over the verdicts that have a checker site."""
    total = sum(n for v, n in counter.items() if v != NO_SITE)
    ok = sum(counter[v] for v in good)
    return ok, total, 100 * ok / max(total, 1)


def keyed(sites, calls):
    """(TS files with a checker row, TS files, calls in them, calls) over the calls of both runs: whether the two sides name
    a file the same way, which no share over the sites can tell."""
    rows = {k[0] for k in sites}
    files = collections.Counter(path_of(c["caller_id"]) for c in calls)
    inside = {f: n for f, n in files.items() if f in rows}
    return len(inside), len(files), sum(inside.values()), sum(files.values())


class Analysis:
    def __init__(self, before, after, sites):
        ts_before, ts_after = in_ts(before), in_ts(after)
        kept = {key(c) for c in after["calls"]}
        had = {key(c) for c in before["calls"]}
        self.added = [c for c in after["calls"] if ts_after(c) and key(c) not in had
                      and c["strategy"].removesuffix("-ambiguous") in TYPED]
        self.dropped = [c for c in before["calls"] if ts_before(c) and key(c) not in kept]
        site_has = {(c["caller_id"], c["line"], called(c)) for c in after["calls"]}
        self.sites = sites
        self.keyed = keyed(sites, [c for c in before["calls"] if ts_before(c)] + [c for c in after["calls"] if ts_after(c)])
        self.added_verdicts = collections.Counter(verdict(c, sites) for c in self.added)
        self.dropped_verdicts = collections.Counter(verdict(c, sites) for c in self.dropped)
        self.fate = collections.Counter(
            ("replaced" if (c["caller_id"], c["line"], called(c)) in site_has else "lost", verdict(c, sites))
            for c in self.dropped)

    def disagreements(self):
        return [c for c in self.added if verdict(c, self.sites) == "checker: another declaration"]


def percent(n, whole):
    return 100 * n / whole if whole else 0.0


def keyed_percent(analysis):
    files_in, files, calls_in, calls = analysis.keyed
    return percent(calls_in, calls) if calls else None


def report(repo, analysis, sample, seed, min_keyed=50.0):
    out = []
    out.append(f"{repo} typed edges the change adds: {len(analysis.added)} {dict(analysis.added_verdicts)}")
    out.append(f"{repo} by-name edges the change drops: {len(analysis.dropped)} {dict(analysis.dropped_verdicts)}")
    ok, total, pct = share(analysis.added_verdicts, *AGREE)
    out.append(f"  added with a checker site: {total} of {len(analysis.added)} ({percent(total, len(analysis.added)):.0f} %), "
               f"agree {ok} ({pct:.1f} % of those, a .d.ts pair and the owner of a member with no symbol count as agreeing)")
    ok, total, pct = share(analysis.dropped_verdicts, *AGREE)
    out.append(f"  dropped with a checker site: {total} of {len(analysis.dropped)} ({percent(total, len(analysis.dropped)):.0f} %), "
               f"the checker agrees with the callee {ok} ({pct:.2f} % of those)")
    files_in, files, calls_in, calls = analysis.keyed
    if calls:
        out.append(f"  the checker has rows for {files_in} of {files} TS files and {calls_in} of {calls} TS calls of the two runs "
                   f"({keyed_percent(analysis):.1f} %)")
        if keyed_percent(analysis) < min_keyed:
            out.append(f"  WARNING: below {min_keyed:g} %: the two sides are probably keyed differently (the repository's path, the extension), "
                       "so every share above is over a small part of the data")
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
    parser = argparse.ArgumentParser(prog="ts_vs_checker.py", add_help=False, usage=(
        "ts_vs_checker.py REPO BEFORE_DIR AFTER_DIR CHECKER.jsonl [--sample N [--seed S]] [--min-keyed PCT] [--strict]"))
    for name in ("repo", "before_dir", "after_dir", "checker"):
        parser.add_argument(name)
    parser.add_argument("--sample", type=int, default=0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--min-keyed", type=float, default=50.0)
    parser.add_argument("--strict", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_:
        print(__doc__, file=sys.stderr)
        return exit_.code
    analysis = Analysis(load(args.before_dir, args.repo), load(args.after_dir, args.repo), checker_sites(args.checker))
    lines = report(args.repo, analysis, args.sample, args.seed, args.min_keyed)
    print("\n".join(lines))
    return 1 if args.strict and any(line.startswith("  WARNING") for line in lines) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
