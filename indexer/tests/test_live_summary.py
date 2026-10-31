"""The live validation's numbers (scripts/live/validate_summary.py) over a synthetic in-flight folder: an after that moves
only the build, the IndexRun counts and the time fields counts as that, and any other difference is counted apart. No
Docker, no live install."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "live"))
import validate_summary as S  # noqa: E402

SNAPSHOTS = '"t", "a", "main", "sha1", "0.2.15+old", FALSE, [], NULL\n"t", "b", "main", "sha2", "0.2.15+old", FALSE, [], NULL\n'
LABELS = '"IndexRun", 10\n"Symbol", 100\n'
RUNS = "tenant, repo, ref, status, n_errors, sha, started\n"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def inflight(tmp_path):
    for side in ("before", "after"):
        write(tmp_path / side / "snapshots.txt", SNAPSHOTS)
        write(tmp_path / side / "labels.txt", LABELS)
        write(tmp_path / side / "symbols.txt", "1\n2\n")
    write(tmp_path / "before" / "golden" / "atlas_status.json", "{}")
    write(tmp_path / "golden-before-after.paths.txt", "=== atlas_status.json\n")
    return tmp_path


def test_a_snapshot_with_an_ok_run_and_no_error_is_reindexed(inflight):
    write(inflight / "indexruns-after-before-picture.txt",
          RUNS + '"t", "a", "main", "ok", 0, "sha1", 1\n"t", "b", "main", "ok", 1, "sha2", 1\n')
    assert S.not_reindexed(inflight) == 1


def test_no_run_at_all_leaves_every_snapshot_pending(inflight):
    assert S.not_reindexed(inflight) == 2


def test_a_snapshot_whose_last_run_failed_is_pending_after_an_earlier_ok_one(inflight):
    write(inflight / "indexruns-after-before-picture.txt",
          RUNS + '"t", "a", "main", "ok", 0, "sha1", 1\n"t", "a", "main", "failed", 1, "sha1", 2\n'
                 '"t", "b", "main", "failed", 1, "sha2", 1\n"t", "b", "main", "ok", 0, "sha2", 2\n')
    assert S.not_reindexed(inflight) == 1


def test_a_snapshot_that_still_holds_the_befores_build_is_stale(inflight):
    builds = "tenant, repo, ref, build\n"
    write(inflight / "builds-after.txt", builds + '"t", "a", "main", "0.2.15+new"\n"t", "b", "main", "0.2.15+old"\n')
    assert S.stale_builds(inflight) == 1
    write(inflight / "builds-after.txt", builds + '"t", "a", "main", "0.2.15+new"\n')
    assert S.stale_builds(inflight) == 1


def test_the_build_and_the_index_run_counts_are_the_only_moves_allowed(inflight):
    write(inflight / "after" / "snapshots.txt", SNAPSHOTS.replace("+old", "+new"))
    write(inflight / "after" / "labels.txt", LABELS.replace("IndexRun\", 10", "IndexRun\", 12"))
    assert S.picture(inflight).endswith("2 differ, 0 differ in more than the build and the IndexRun counts")


@pytest.mark.parametrize("name,text", [("snapshots.txt", SNAPSHOTS.replace("sha1", "sha9")),
                                       ("labels.txt", LABELS.replace("100", "101")),
                                       ("symbols.txt", "1\n3\n")])
def test_any_other_move_is_counted_apart(inflight, name, text):
    write(inflight / "after" / name, text)
    assert S.picture(inflight).endswith("1 differ, 1 differ in more than the build and the IndexRun counts")


def test_time_and_build_fields_of_an_answer_are_allowed_and_a_status_is_not(inflight):
    write(inflight / "golden-before-after.paths.txt",
          "=== atlas_status.json\n  .content.indexer_build: a -> b\n  .content.snapshots[0].age_min: 1 -> 2\n"
          "  .content.status: ok -> stale\n")
    assert S.answers(inflight) == "answers: 1 files, 1 differ, 1 path(s) outside the time, build and refresh fields"
