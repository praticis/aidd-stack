"""The gate on the scorecard (judgment/scorecard.py, run by checks/reference.sh in the micro job): its exit code and the
floors the change lowers, under the pull request's labels. Read by gates.py.

A number under its floor fails, whatever the labels: the scorecard is run with the floors of the branch, so a change that
means to lower one has edited its line, and what is left to judge here is that the edit is declared. A lowered floor needs
the `graph-change` label (the label alone frees any change of the graph, the line alone could be a slip, together they are
a decision), and a refactor lowers none."""
from __future__ import annotations


def judge(rc: int | None, lowered: int | None, labels: set[str]) -> tuple[bool, str]:
    """(ok, the line gates.py prints). `rc` is the scorecard's exit code and `lowered` how many floors the change
    lowers; None for either is a run that did not measure them (a local run), which has nothing to say."""
    if rc is None:
        return True, ""
    if rc == 1:
        return False, ("FAIL: a number of the graph is under its floor (the micro job's `reference.txt` lists them). Fix the change, "
                       "or lower the floor on its line of `indexer/scripts/checks/reference_floors.txt`, under the `graph-change` label")
    if rc != 0:
        return False, "FAIL: the scorecard did not run (see the micro job)"
    if not lowered:
        return True, "pass: every number of the graph holds its floor"
    if "refactor" in labels:
        return False, f"FAIL: {lowered} floor(s) lowered in a `refactor`, which changes nothing"
    if "graph-change" not in labels:
        return False, (f"FAIL: {lowered} floor(s) lowered without the `graph-change` label. Judge the drop; when it is right, "
                       "add the label and re-run this job")
    return True, f"pass: every number holds its floor, {lowered} floor(s) lowered under the `graph-change` label"
