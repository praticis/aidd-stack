"""The numbers of a live validation (docs/indexer/method.md §4.7 and §4.8), read from the in-flight folder. Counts only:
the live install's tenants, repositories and answers stay out of the output.

usage: validate_summary.py not-reindexed INFLIGHT   how many snapshots' last run since the before is not ok
       validate_summary.py stale-builds INFLIGHT    how many snapshots still hold the build they had in the before
       validate_summary.py before INFLIGHT          the dry-runs, the graph against them, the answers, the picture
       validate_summary.py after INFLIGHT           the picture, the answers and the runs, against the before"""
import csv
import sys
from pathlib import Path

# the fields of an answer that move with time or with the build, and nothing else
MOVING = ("age_min", "last_finished_at", "last_success_at", "indexed_at", "indexer_build", "refresh.changed",
          "started_at", "finished_at", "success_age_min")
BUILD_COLUMN = 4
COUNTED = ("symbols", "calls_edges", "imports_edges", "hierarchy_edges", "modules", "violations")


def lines(path: Path) -> list[str]:
    return path.read_text().splitlines()


def rows(text_lines: list[str]) -> list[list[str]]:
    return sorted(csv.reader(text_lines, skipinitialspace=True))


def snapshots(inflight: Path) -> set[tuple[str, ...]]:
    return {tuple(r[:3]) for r in rows(lines(inflight / "before" / "snapshots.txt"))}


def not_reindexed(inflight: Path) -> int:
    """A snapshot is re-indexed when its last run since the before is ok and has no error: an earlier ok run may be the
    old code's."""
    runs = inflight / "indexruns-after-before-picture.txt"
    last: dict[tuple[str, ...], list[str]] = {}
    for r in rows(lines(runs)[1:]) if runs.exists() else []:
        if tuple(r[:3]) not in last or r[6] > last[tuple(r[:3])][6]:
            last[tuple(r[:3])] = r
    return len(snapshots(inflight) - {k for k, r in last.items() if r[3] == "ok" and r[4] == "0"})


def stale_builds(inflight: Path) -> int:
    """Snapshots whose build in the graph is still the one the before shows: a refresh before the reinstall wrote them
    with the old code."""
    before = {tuple(r[:3]): r[BUILD_COLUMN] for r in rows(lines(inflight / "before" / "snapshots.txt"))}
    now = {tuple(r[:3]): r[3] for r in rows(lines(inflight / "builds-after.txt")[1:])}
    return sum(now.get(k, build) == build for k, build in before.items())


def only_index_runs(before: list[str], after: list[str]) -> bool:
    changed = [x for x in before if x not in after] + [x for x in after if x not in before]
    return all("IndexRun" in x for x in changed)


def only_build(before: list[str], after: list[str]) -> bool:
    a, b = rows(before), rows(after)
    return len(a) == len(b) and all(
        all(x == y for i, (x, y) in enumerate(zip(ra, rb)) if i != BUILD_COLUMN) for ra, rb in zip(a, b))


def allowed(name: str, before: list[str], after: list[str]) -> bool:
    if name == "labels.txt":
        return only_index_runs(before, after)
    return name == "snapshots.txt" and only_build(before, after)


def picture(inflight: Path) -> str:
    files = sorted((inflight / "before").glob("*.txt"))
    differing = [f.name for f in files if lines(f) != lines(inflight / "after" / f.name)]
    stray = [n for n in differing
             if not allowed(n, lines(inflight / "before" / n), lines(inflight / "after" / n))]
    return (f"picture: {len(files)} files, {len(files) - len(differing)} identical, {len(differing)} differ, "
            f"{len(stray)} differ in more than the build and the IndexRun counts")


def answers(inflight: Path) -> str:
    differ, stray, current = set(), 0, ""
    for line in lines(inflight / "golden-before-after.paths.txt"):
        if line.startswith("==="):
            current = line.split()[1]
        elif line.strip():
            differ.add(current)
            stray += not any(m in line for m in MOVING)
    total = len(list((inflight / "before" / "golden").glob("*.json")))
    return f"answers: {total} files, {len(differ)} differ, {stray} path(s) outside the time, build and refresh fields"


def mismatching(path: Path) -> str:
    last = [x for x in lines(path) if x.startswith("mismatching snapshots")]
    return f"graph against the dry-runs: {last[-1].rsplit(':', 1)[1].strip() if last else '?'} mismatching snapshot(s)"


def before(inflight: Path) -> None:
    sections = lines(inflight / "dry_sections.txt")
    identical = sum(x.endswith(": identical") for x in sections)
    failed = [x for x in lines(inflight / "dryrun.txt") if " rc=" in x and " rc=0 " not in x]
    golden = lines(inflight / "golden_before.txt")
    answered = sum("error=False" in x for x in golden)
    counts = dict(x.split(": ", 1) for x in lines(inflight / "picture_before.txt") if ": " in x)
    print(f"dry-runs: {len(sections)} snapshots, main and branch identical in {identical}, {len(failed)} run(s) failed")
    print(mismatching(inflight / "graph_vs_dry.txt"))
    print(f"golden answers: {len(golden)} calls, {answered} answered, {len(golden) - answered} refused or failed")
    print("picture: " + ", ".join(f"{k} {counts[k].split()[0]}" for k in COUNTED if k in counts))


def after(inflight: Path) -> None:
    print(picture(inflight))
    print(mismatching(inflight / "graph_vs_dry.before-after.txt"))
    print(answers(inflight))
    total = len(snapshots(inflight))
    print(f"index runs since the before: {total - not_reindexed(inflight)} of {total} snapshots ok, no error")


def main(argv: list[str]) -> int:
    commands = {"before": before, "after": after}
    counts = {"not-reindexed": not_reindexed, "stale-builds": stale_builds}
    if len(argv) == 3 and argv[1] in counts:
        print(counts[argv[1]](Path(argv[2])))
        return 0
    if len(argv) != 3 or argv[1] not in commands:
        print(__doc__, file=sys.stderr)
        return 2
    commands[argv[1]](Path(argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
