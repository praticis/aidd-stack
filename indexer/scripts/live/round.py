"""The draft of a golden round and of its history line, from a validated PR's in-flight folder (docs/indexer/method.md §4.9).

   round.py INFLIGHT --pr N --number K --date YYYY-MM-DD --what "TEXT" [--merge SHA]

INFLIGHT is the folder `validate.sh after` left (inflight/, or merged/ after the rotation). K is the round's number (the one
after the last round in docs/golden-questions.md and in the pending docs); TEXT says in one sentence what the PR changed;
SHA is the commit that merged it. It prints the round, then a line of `---`, then the history line. Only counts, snapshot
numbers, the names of the picture's lists, the names of the MCP's tools and build ids appear: never a tenant, a repository
or a label, which the live data holds. The judgment ("what the round shows") and the sentence of what changed are the
author's: the draft marks them."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_summary as vs  # noqa: E402

ONES = ("zeroth first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth "
        "sixteenth seventeenth eighteenth nineteenth").split()
TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety"}
QUESTIONS = (("q1", "Q1 `who_consumes`, in lower case and in the code's case"), ("q2", "Q2 `http_map`"), ("q3", "Q3 map"),
             ("q4", "Q4a and Q4b `impact_of`"), ("q5", "Q5 `ref_diff`"))


def ordinal(n: int) -> str:
    if n < 20:
        return ONES[n]
    tens, ones = divmod(n, 10)
    return f"{TENS[tens]}-{ONES[ones]}" if ones else TENS[tens].replace("y", "ieth")


def words(n: int) -> str:
    return "all" if n == 0 else str(n)


def commits(inflight: Path) -> dict[str, str]:
    return dict(line.split(None, 1) for line in vs.lines(inflight / "commits.txt") if " " in line)


def picture_counts(path: Path) -> dict[str, int]:
    found = dict(x.split(": ", 1) for x in vs.lines(path) if ": " in x)
    return {k: int(found[k].split()[0]) for k in vs.COUNTED if k in found}


def numbers(counts: dict[str, int]) -> str:
    names = {"symbols": "symbols", "calls_edges": "`CALLS`", "imports_edges": "`IMPORTS`", "hierarchy_edges": "types' and overrides' edges",
             "modules": "modules", "violations": "violations"}
    return ", ".join(f"{counts[k]:,} {names[k]}" for k in vs.COUNTED if k in counts)


def dry_runs(inflight: Path) -> tuple[int, list[int]]:
    sections = vs.lines(inflight / "dry_sections.txt")
    differing = [int(re.match(r"snapshot (\d+)", x).group(1)) for x in sections if not x.endswith(": identical")]
    return len(sections), differing


def listing(numbers_: list[int]) -> str:
    head = ", ".join(map(str, numbers_[:-1]))
    return f"{head} and {numbers_[-1]}" if head else str(numbers_[0])


def mismatch(path: Path) -> int:
    return int(vs.mismatching(path).split(":", 1)[1].split()[0])


def builds(inflight: Path) -> tuple[str, str]:
    before = {r[vs.BUILD_COLUMN] for r in vs.rows(vs.lines(inflight / "before" / "snapshots.txt"))}
    after = {r[3] for r in vs.rows(vs.lines(inflight / "builds-after.txt")[1:])}
    return ", ".join(sorted(before)).replace('"', ""), ", ".join(sorted(after)).replace('"', "")


def picture_differences(inflight: Path) -> tuple[list[str], int, int]:
    files = sorted((inflight / "before").glob("*.txt"))
    differing = [f for f in files if vs.lines(f) != vs.lines(inflight / "after" / f.name)]
    stray = [f for f in differing if not vs.allowed(f.name, vs.lines(f), vs.lines(inflight / "after" / f.name))]
    return [f.stem for f in differing], len(files), len(stray)


def answers(inflight: Path) -> dict[str, object]:
    """The calls, how many answered, the tool that refuses, and per tool and per question what differs, and how."""
    before = [x.split() for x in vs.lines(inflight / "golden_before.txt")]
    refused = sorted({row[1] for row in before if "error=True" in row})
    differ, stray, current = {}, set(), ""
    for line in vs.lines(inflight / "golden-before-after.paths.txt"):
        if line.startswith("==="):
            current = line.split()[1].removesuffix(".json")
        elif line.strip():  # a path that differs in the answer of `current`
            differ[current] = True
            if not any(m in line for m in vs.MOVING):
                stray.add(current)
    tool = {row[0]: row[1] for row in before}
    return {"calls": len(before), "answered": sum("error=False" in row for row in before), "refused": refused,
            "differ": differ, "stray": stray, "tool": tool}


def tool_counts(labels: list[str], tool: dict[str, str]) -> str:
    names = sorted({tool[x] for x in labels if x in tool})
    return ", ".join(f"`{n}` ({sum(tool.get(x) == n for x in labels)})" for n in names)


def question_row(prefix: str, title: str, info: dict) -> str:
    labels = [x for x in info["tool"] if x.startswith(prefix)]
    differ = [x for x in labels if x in info["differ"]]
    if any(x in info["stray"] for x in differ):
        return f"| {title} | ⚠ differs: judge it at the source |"
    return f"| {title} | ✅ the same{' but its time fields' if differ else ''}{' on the 3 tenants' if prefix == 'q3' else ''} |"


def round_text(inflight: Path, pr: int, number: int, date: str, what: str, merge: str) -> str:
    c, (n, differing), (old, new) = commits(inflight), dry_runs(inflight), builds(inflight)
    snaps = vs.snapshots(inflight)
    tenants, runs, info = len({s[0] for s in snaps}), vs.last_runs(inflight), answers(inflight)
    before_counts, after_counts = picture_counts(inflight / "picture_before.txt"), picture_counts(inflight / "picture_after.txt")
    lists, total, stray = picture_differences(inflight)
    same_calls = info["calls"] - len(info["differ"])
    moving = [x for x in info["differ"] if x not in info["stray"]]
    identical = f"identical in {words(n - len(differing)) if differing else 'all'} {'of the ' + str(n) if differing else str(n)} snapshots"
    if differing:
        identical += f" and differ in {listing(differing)}"
    out = [f"## {ordinal(number).capitalize()} round: validating PR #{pr} on a live install ({date}, build `{old}` to `{new}`)", "",
           f"What changed since the {ordinal(number - 1)} round: {what or '**TODO: one sentence, what PR #%d changed**' % pr}. "
           f"The same {tenants} tenants and {len(snaps)} snapshots, and {info['calls']} calls.", "",
           f"- **Before the reinstall and the merge, read-only:** the install ran `main`'s code (`{c['before_commit'][:7]}`). The dry-runs of "
           f"`main` and of the PR's head (`{c['after_commit'][:7]}`) on each snapshot, at its sha, are {identical}, and the live graph "
           f"held `main`'s dry-run on every snapshot ({mismatch(inflight / 'graph_vs_dry.txt')} mismatching): {numbers(before_counts)}.",
           f"- **After the author's reinstall from `main` (`{merge[:7] or '<the merge>'}`, whose tree is the PR head's):** the {len(snaps)} snapshots "
           f"ran since the before, {'all ok' if vs.failed_runs(inflight) == 0 else str(vs.failed_runs(inflight)) + ' not ok'} "
           f"({len(runs)} of {len(snaps)}), and {'each holds the new build' if vs.stale_builds(inflight) == 0 else str(vs.stale_builds(inflight)) + ' still hold the old build'}.", "",
           f"**The picture of the graph** differs in {len(lists)} of its {total} lists ({', '.join(lists) or 'none'}), "
           f"{'none' if not stray else stray} of them by more than the build and the `IndexRun` counts"
           f"{'' if before_counts == after_counts else ': ' + numbers(before_counts) + ' to ' + numbers(after_counts)}. The graph after "
           f"holds the branch's dry-run on every snapshot ({mismatch(inflight / 'graph_vs_dry.before-after.txt')} mismatching).", "",
           f"**The {info['calls']} calls** all reached the MCP. {info['answered']} gave no error"
           f"{' and ' + ', '.join('`' + t + '`' for t in info['refused']) + ' still refuses a write' if info['refused'] else ''}. "
           f"{same_calls} answers are the same field by field. {len(moving)} differ only in their time, build and refresh fields"
           f"{': ' + tool_counts(moving, info['tool']) if moving else ''}"
           f"{'; ' + str(len(info['stray'])) + ' differ in more: judge them at the source' if info['stray'] else ''}.", "",
           "| Q | Result |", "|---|---|"]
    out += [question_row(p, t, info) for p, t in QUESTIONS]
    out += ["", "**What the round shows.** **TODO: what the numbers say, in the author's words.**"]
    return "\n".join(out)


def history_line(inflight: Path, pr: int, number: int, date: str) -> str:
    n, differing = dry_runs(inflight)
    info, counts = answers(inflight), picture_counts(inflight / "picture_after.txt")
    moving = len([x for x in info["differ"] if x not in info["stray"]])
    dry = f"identical in all {n} snapshots" if not differing else f"identical in {n - len(differing)} of the {n} snapshots and differ in {listing(differing)}"
    return (f"- {date}: PR #{pr} is validated on a live install (the {ordinal(number)} round). The dry-runs of `main` and of the PR's head are "
            f"{dry}. The graph after holds them on each snapshot ({mismatch(inflight / 'graph_vs_dry.before-after.txt')} mismatching): "
            f"{numbers(counts)}; of the {info['calls']} calls, {info['calls'] - len(info['differ'])} are the same and {moving} differ only "
            f"in their time, build and refresh fields.")


def main(argv: list[str]) -> int:
    flags = dict(zip(argv[1:], argv[2:]))
    needed = ("--pr", "--number", "--date")
    if len(argv) < 2 or not Path(argv[0]).is_dir() or any(k not in flags for k in needed) or not flags["--pr"].isdigit() \
            or not flags["--number"].isdigit() or not re.fullmatch(r"\d{4}-\d\d-\d\d", flags["--date"]):
        print(__doc__, file=sys.stderr)
        return 2
    inflight, pr, number, date = Path(argv[0]), int(flags["--pr"]), int(flags["--number"]), flags["--date"]
    print(round_text(inflight, pr, number, date, flags.get("--what", ""), flags.get("--merge", "")))
    print("\n---\n")
    print(history_line(inflight, pr, number, date))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
