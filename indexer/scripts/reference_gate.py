"""The gate on the scorecard (judgment/scorecard.py, run by checks/reference.sh in the micro job): its exit code and the
bounds the change lowers, under the pull request's labels. Read by gates.py.

A count past its bound fails, whatever the labels: the scorecard is run with the bounds of the branch, so a change that means
to move one has edited its line, and what is left to judge here is that the edit is declared. A lowered bound (a floor that
falls, a ceiling that rises, a line that goes) and a win lost (a site where the base has a confirmed typed edge and the tree
has none: the scorecard's exit code 3) each need the `graph-change` label: the label alone frees any change of the graph, the
line alone could be a slip, together they are a decision. A refactor changes nothing, so it does neither."""
from __future__ import annotations

PAST = ("FAIL: a count of the graph is past its bound (the micro job's `reference.txt` lists them). Fix the change, or move the "
        "bound on its line of `indexer/scripts/checks/reference_floors.txt`, under the `graph-change` label")


def moved(lost: bool, lowered: int) -> str:
    parts = ([f"{lowered} bound(s) lowered"] if lowered else []) + (["wins lost"] if lost else [])
    return " and ".join(parts)


def judge(rc: int | None, lowered: int | None, labels: set[str]) -> tuple[bool, str]:
    """(ok, the line gates.py prints). `rc` is the scorecard's exit code and `lowered` how many bounds the change lowers; None
    for the code is a run that did not measure (a local run), which has nothing to say."""
    if rc is None:
        return True, ""
    if rc == 1:
        return False, PAST
    if rc not in (0, 3):
        return False, "FAIL: the scorecard did not run (see the micro job)"
    what = moved(rc == 3, lowered or 0)
    if not what:
        return True, "pass: every count of the graph holds its bound and no win is lost"
    if "refactor" in labels:
        return False, f"FAIL: {what} in a `refactor`, which changes nothing"
    if "graph-change" not in labels:
        return False, f"FAIL: {what} without the `graph-change` label. Judge it; when it is right, add the label and re-run this job"
    return True, f"pass: every count holds its bound; {what}, under the `graph-change` label"
