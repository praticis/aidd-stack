"""The cost of a change in a pass over a repository: main against the branch, in pairs, from the runs corpus.sh left.

   cost_pairs.py HOME PREFIX PAIRS
   cost_pairs.py HOME --main LABEL... --branch LABEL...

HOME is the corpus folder (~/.cache/aidd-corpus); the runs are PREFIX-m1 and PREFIX-b1 (main's and the branch's, first pair), then
PREFIX-m2 and PREFIX-b2, and so on, or the labels given in order, each with runs/<label>.logs/summary.txt, whose lines are
`repo ok SECONDSs PEAK_BYTES`.
For each repo it prints the change in time of each pair, in per cent; the median of the first three pairs and of all of them;
and the change in the median peak memory. A repo that takes under 30 s on main is marked: a second of noise decides there, so it is
reported and does not decide."""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

NOISY_BELOW = 30  # seconds on main


def read(home: str, label: str) -> dict[str, tuple[int, int]]:
    rows = {}
    summary = Path(home) / "runs" / f"{label}.logs" / "summary.txt"
    for line in summary.read_text().splitlines() if summary.is_file() else []:  # a run that ended in an error has none
        repo, status, seconds, peak = (line.split() + ["", "", "0s", "0"])[:4]
        if status == "ok":
            rows[repo] = (int(seconds.rstrip("s")), int(peak or 0))
    return rows


def change(was: float, now: float) -> float:
    return 100 * (now - was) / was if was else 0.0


def report(home: str, main_labels: list[str], branch_labels: list[str]) -> list[str]:
    main = [read(home, label) for label in main_labels]
    branch = [read(home, label) for label in branch_labels]
    out = []
    for repo in sorted(set.intersection(*(set(r) for r in main + branch))):
        deltas = [change(m[repo][0], b[repo][0]) for m, b in zip(main, branch)]
        peaks_m, peaks_b = [m[repo][1] for m in main], [b[repo][1] for b in branch]
        first = statistics.median(deltas[:3])
        line = (f"{repo}: time {' '.join(f'{d:+.1f}' for d in deltas)} % | median of the first three {first:+.1f} %, of all "
                f"{statistics.median(deltas):+.1f} % | memory {change(statistics.median(peaks_m), statistics.median(peaks_b)):+.1f} %")
        if statistics.median(m[repo][0] for m in main) < NOISY_BELOW:
            line += " (under 30 s on main: reported, not deciding)"
        out.append(line)
    return out


def labels(args: list[str]) -> tuple[list[str], list[str]] | None:
    """The labels of main's runs and of the branch's, from `PREFIX PAIRS` or from --main and --branch, or None."""
    if "--main" in args and "--branch" in args:
        m, b = args.index("--main"), args.index("--branch")
        main_labels, branch_labels = args[m + 1:b], args[b + 1:]  # --branch first leaves main's list empty
        return (main_labels, branch_labels) if main_labels and len(main_labels) == len(branch_labels) else None
    if len(args) == 2 and args[1].isdigit() and int(args[1]) >= 1:
        n = int(args[1])
        return [f"{args[0]}-m{i}" for i in range(1, n + 1)], [f"{args[0]}-b{i}" for i in range(1, n + 1)]
    return None


def main(argv: list[str]) -> int:
    chosen = labels(argv[1:]) if argv else None
    if chosen is None:
        print(__doc__, file=sys.stderr)
        return 2
    lines = report(argv[0], *chosen)
    print("\n".join(lines) if lines else "no repo has a run in every pair")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
