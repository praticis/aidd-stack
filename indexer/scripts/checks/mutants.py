"""Each rule of a change broken once, and the tests asked whether they notice.

  checks/mutants.sh MUTANTS.py [ID ...] [--allow ID]... [--timeout SECONDS] [--no-baseline] [--tests ARG ...]
                                                                              (--tests takes the rest of the line)

MUTANTS.py is Python the author wrote, and it is run as such. It defines MUTANTS, a non-empty list of (name, file, old, new):
`file` is a path under indexer/, `old` a text that appears in it exactly once and `new` what it becomes; the name starts with
the mutant's id. It may define TESTS, the arguments given to test.sh (default: the whole suite). The tool first runs the tests
on an unchanged copy, which must pass (--no-baseline skips it): a suite already red would kill every mutant. Then, for each
mutant, it copies indexer/, makes the one change in the copy and runs test.sh on the copy with -x.

A mutant DIES if pytest ran and a test failed or errored, SURVIVES if pytest ran and every test passed, and is a TIMEOUT, counted
as dead, if the run has no result in --timeout seconds (default 1800). It is BROKEN when pytest did not run (a bad --tests path,
an image that does not build): that is no verdict. A survivor is an equivalent change (say why in the PR, and pin it if a test
can), a case that is missing (add it) or a guard nothing reaches (remove it).

Exit status: 0 when every mutant not named by --allow dies; 1 when one survives; 2 when the run cannot give a verdict: the file
or an anchor is wrong, the baseline is red, or a mutant is BROKEN. Status 1 never means anything but a survivor."""
from __future__ import annotations

import argparse
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

INDEXER = Path(os.environ.get("AIDD_MUTANTS_INDEXER") or Path(__file__).resolve().parents[2])
SKIP = shutil.ignore_patterns("__pycache__", ".pytest_cache", "bin", "obj", ".DS_Store")
# the line pytest ends with: it ran. Docker or the shell failing before it never prints one
RAN = re.compile(r"\b\d+ (?:failed|passed|errors?|skipped|deselected|xfailed|xpassed)\b[^\n]* in [\d.]+s|no tests ran in [\d.]+s")


class Mutant(NamedTuple):
    name: str
    path: str
    old: str
    new: str

    @property
    def id(self) -> str:
        return self.name.split()[0]


class MutantsError(Exception):
    """The author's error, or an environment that cannot give a verdict: status 2, never a survivor."""


def load(path: str) -> tuple[list[Mutant], list[str]]:
    try:
        defined = runpy.run_path(path)
    except Exception as error:  # the file is the author's code: whatever it raises, it is theirs to fix
        raise MutantsError(f"cannot read {path}: {type(error).__name__}: {error}") from error
    raw = defined.get("MUTANTS")
    if not isinstance(raw, list) or not raw:
        raise MutantsError(f"{path} must define MUTANTS, a non-empty list of (name, file, old, new)")
    mutants = []
    for item in raw:
        if not (isinstance(item, (tuple, list)) and len(item) == 4 and all(isinstance(x, str) for x in item)
                and item[0].strip() and item[1] and item[2]):
            raise MutantsError(f"not a (name, file, old, new) of strings, with a name, a file and an anchor: {str(item)[:90]}")
        mutants.append(Mutant(*item))
    ids = [m.id for m in mutants]
    if len(set(ids)) != len(ids):
        raise MutantsError(f"two mutants share an id: {sorted(i for i in set(ids) if ids.count(i) > 1)}")
    return mutants, list(defined.get("TESTS", ["tests"]))


def apply(mutant: Mutant, root: Path) -> None:
    target = (root / mutant.path).resolve()
    if root.resolve() not in target.parents:
        raise MutantsError(f"{mutant.name}: {mutant.path} is outside the tree")
    if not target.is_file():
        raise MutantsError(f"{mutant.name}: no file {mutant.path} under indexer/")
    text = target.read_text()
    found = text.count(mutant.old)
    if found != 1:
        raise MutantsError(f"{mutant.name}: the anchor is found {found} times in {mutant.path}; it must be found once")
    target.write_text(text.replace(mutant.old, mutant.new))


def first_failure(output: str) -> str:
    return next((line for line in output.splitlines() if line.startswith(("FAILED", "ERROR"))), "")


def verdict(returncode: int, output: str, timeout: int | None = None) -> tuple[str, str]:
    last = output.strip().splitlines()[-1] if output.strip() else "no output"
    if timeout is not None:
        return "TIMEOUT", f"no result in {timeout} s"
    if RAN.search(output):
        failure = first_failure(output)
        if returncode == 0:
            return "SURVIVES", last
        if failure:
            return "DIES", failure
    return "BROKEN", f"pytest did not give a result (status {returncode}): {last}"


def run_tests(root: Path, tests: list[str], limit: int) -> tuple[int, str, int | None]:
    proc = subprocess.Popen([str(root / "scripts" / "test.sh"), *tests, "-x", "--no-header", "-rf"], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        output, _ = proc.communicate(timeout=limit)
        return proc.returncode, output, None
    except subprocess.TimeoutExpired:
        proc.terminate()  # test.sh execs docker: its SIGTERM reaches the container, a SIGKILL would not
        try:
            output, _ = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            output, _ = proc.communicate()
        return proc.returncode, output or "", limit


def in_copy(mutant: Mutant | None, tests: list[str], limit: int) -> tuple[str, str]:
    work = Path(tempfile.mkdtemp(prefix="mutant-", dir=os.environ.get("AIDD_MUTANTS_DIR")))
    try:
        shutil.copytree(INDEXER, work / "indexer", ignore=SKIP)
        if mutant:
            apply(mutant, work / "indexer")
        return verdict(*run_tests(work / "indexer", tests, limit))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def select(mutants: list[Mutant], ids: list[str], allowed: list[str]) -> list[Mutant]:
    unknown = sorted((set(ids) | set(allowed)) - {m.id for m in mutants})
    if unknown:
        raise MutantsError(f"no mutant has the id {', '.join(unknown)}")
    return [m for m in mutants if not ids or m.id in ids]


def status(results: list[tuple[Mutant, str]], allowed: list[str]) -> int:
    count = lambda state: sum(s == state for _, s in results)  # noqa: E731
    survivors = [m for m, s in results if s == "SURVIVES"]
    kept = [m for m in survivors if m.id in allowed]
    print(f"{len(results)} mutants, {count('DIES') + count('TIMEOUT')} die ({count('TIMEOUT')} by timeout), "
          f"{len(survivors)} survive ({len(kept)} allowed), {count('BROKEN')} broken")
    if count("BROKEN"):
        return 2
    return 1 if len(survivors) > len(kept) else 0


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("file")
    parser.add_argument("ids", nargs="*")
    parser.add_argument("--allow", action="append", default=[], metavar="ID")
    parser.add_argument("--timeout", type=int, default=1800, metavar="SECONDS")
    parser.add_argument("--no-baseline", dest="baseline", action="store_false")
    parser.add_argument("--tests", nargs=argparse.REMAINDER, default=None, metavar="ARG")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse(argv)
    try:
        mutants, tests = load(args.file)
        chosen = select(mutants, args.ids, args.allow)
        tests = args.tests or tests
        if args.baseline:
            state, detail = in_copy(None, tests, args.timeout)
            if state != "SURVIVES":
                raise MutantsError(f"the tests do not pass on the unchanged tree, so no mutant can be judged: {state}: {detail}")
        results = []
        for mutant in chosen:
            state, detail = in_copy(mutant, tests, args.timeout)
            results.append((mutant, state))
            print(f"{mutant.name}: {state} | {detail[:170]}", flush=True)
    except MutantsError as error:
        print(f"mutants: {error}", file=sys.stderr)
        return 2
    return status(results, args.allow)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
