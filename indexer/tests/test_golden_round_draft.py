"""The draft of a golden round (scripts/live/round.py), on an in-flight folder made for the purpose.

The folder holds invented tenants, repositories and labels, and the tests check that none of them reaches the output: the draft
may carry counts, snapshot numbers, the picture's list names, tool names and build ids, and nothing the live data names."""
import importlib.util
import sys
from pathlib import Path

import pytest

LIVE = Path(__file__).resolve().parent.parent / "scripts" / "live"
sys.path.insert(0, str(LIVE))
spec = importlib.util.spec_from_file_location("round_draft", LIVE / "round.py")
draft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(draft)

SNAPS = (("acme", "payroll-app", "main"), ("acme", "billing", "main"), ("globex", "ledger", "main"))
SECRETS = ("acme", "globex", "payroll-app", "billing", "ledger", "secret_label", "other_label", "refuse_label")
OLD, NEW = "0.2.15+aaaaaaaaaaaa", "0.2.15+bbbbbbbbbbbb"


def snapshot_rows(build):
    return [f'"{t}", "{r}", "{ref}", "s{i}", "{build}", FALSE, [], NULL' for i, (t, r, ref) in enumerate(SNAPS, 1)]


def make(tmp_path, mismatch_after=0, dry=("identical", "identical", "identical"), golden_differ=(), stale=False, failed=False, symbols=(100, 100)):
    d = tmp_path / "inflight"
    for sub in ("before", "after", "before/golden"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    (d / "commits.txt").write_text(f"before_commit {'a' * 40}\nafter_commit {'b' * 40}\ntools_commit {'b' * 40}\n")
    (d / "before" / "snapshots.txt").write_text("\n".join(snapshot_rows(OLD)) + "\n")
    (d / "after" / "snapshots.txt").write_text("\n".join(snapshot_rows(OLD if stale else NEW)) + "\n")
    for name, was, now in (("labels.txt", '"acme", "IndexRun", 10', '"acme", "IndexRun", 13'), ("calls.txt", "x", "x")):
        (d / "before" / name).write_text(was + "\n")
        (d / "after" / name).write_text(now + "\n")
    (d / "builds-after.txt").write_text("tenant, repo, ref, build\n" + "".join(
        f'"{t}", "{r}", "{ref}", "{OLD if stale else NEW}"\n' for t, r, ref in SNAPS))
    for name, n in (("picture_before.txt", symbols[0]), ("picture_after.txt", symbols[1])):
        (d / name).write_text(f"symbols: {n} rows\ncalls_edges: 500 rows\nimports_edges: 200 rows\nhierarchy_edges: 7 rows\nmodules: 30 rows\nviolations: 0 rows\n")
    (d / "graph_vs_dry.txt").write_text("snapshot 1: all match\n\nmismatching snapshots: 0\n")
    (d / "graph_vs_dry.before-after.txt").write_text(f"snapshot 1: all match\n\nmismatching snapshots: {mismatch_after}\n")
    (d / "dry_sections.txt").write_text("".join(f"snapshot {i} (yaml 5): {state}\n" for i, state in enumerate(dry, 1)))
    calls = [("atlas_status", "atlas_status", "False"), ("q1_secret_label", "who_consumes", "False"), ("q2_other_label", "http_map", "False"),
             ("q3_map_acme", "repo_map", "False"), ("q4a_impact", "impact_of", "False"), ("q5_ref_diff", "ref_diff", "False"),
             ("refuse_label", "cypher_readonly", "True")]
    for name in ("golden_before.txt", "golden_after.txt"):
        (d / name).write_text("".join(f"{label}  {tool}  error={err} 100 bytes\n" for label, tool, err in calls))
    paths = []
    for label, moving in golden_differ:
        paths += [f"=== {label}.json", "  .content.indexer_build: a -> b" if moving else "  .content.symbols[0].name: a -> b"]
    (d / "golden-before-after.paths.txt").write_text("\n".join(paths) + "\n")
    runs = ["tenant, repo, ref, status, n_errors, sha, started"]
    for i, (tenant, repo, ref) in enumerate(SNAPS):
        runs.append(f'"{tenant}", "{repo}", "{ref}", "{"error" if failed and i == 1 else "ok"}", {1 if failed and i == 1 else 0}, "sha", 2026-11-08T10:00:0{i}Z')
    (d / "indexruns-after-before-picture.txt").write_text("\n".join(runs) + "\n")
    return d


def run(d, **kw):
    args = {"pr": 85, "number": 43, "date": "2026-11-08", "what": "a `fix(typescript)` that changes X", "merge": "8748babcdef"}
    args.update(kw)
    return draft.round_text(d, args["pr"], args["number"], args["date"], args["what"], args["merge"]), \
        draft.history_line(d, args["pr"], args["number"], args["date"])


def test_the_title_the_builds_the_commits_and_the_counts_of_a_round_with_nothing_changed(tmp_path):
    text, _ = run(make(tmp_path))
    assert text.startswith(f"## Forty-third round: validating PR #85 on a live install (2026-11-08, build `{OLD}` to `{NEW}`)")
    assert "What changed since the forty-second round: a `fix(typescript)` that changes X. The same 2 tenants and 3 snapshots, and 7 calls." in text
    assert "the install ran `main`'s code (`aaaaaaa`)" in text and "the PR's head (`bbbbbbb`)" in text and "reinstall from `main` (`8748bab`" in text
    assert "identical in all 3 snapshots" in text and "(0 mismatching)" in text
    assert "100 symbols, 500 `CALLS`, 200 `IMPORTS`, 7 types' and overrides' edges, 30 modules, 0 violations" in text
    assert "the 3 snapshots ran since the before, all ok (3 of 3), and each holds the new build" in text


def test_the_picture_names_the_lists_that_differ_and_whether_any_differs_in_more_than_the_build_and_the_run_counts(tmp_path):
    text, _ = run(make(tmp_path))
    assert "differs in 2 of its 3 lists (labels, snapshots), none of them by more than the build and the `IndexRun` counts" in text
    d = make(tmp_path / "b", symbols=(100, 103))
    (d / "before" / "calls.txt").write_text("x\n")
    (d / "after" / "calls.txt").write_text("y\n")
    text, _ = run(d)
    assert "differs in 3 of its 3 lists (calls, labels, snapshots), 1 of them by more than the build" in text
    assert "100 symbols" in text and "103 symbols" in text and " to " in text


def test_a_snapshot_whose_dry_runs_differ_is_named_by_its_number(tmp_path):
    text, history = run(make(tmp_path, dry=("identical", "differs: CALLS", "differs: CALLS")))
    assert "identical in 1 of the 3 snapshots and differ in 2 and 3" in text
    assert "identical in 1 of the 3 snapshots and differ in 2 and 3" in history


def test_the_calls_the_tools_that_differ_only_in_time_and_the_one_that_refuses_a_write(tmp_path):
    text, _ = run(make(tmp_path, golden_differ=(("atlas_status", True), ("q5_ref_diff", True), ("q3_map_acme", True))))
    assert "7 calls" in text and "6 gave no error and `cypher_readonly` still refuses a write" in text
    assert "4 answers are the same field by field. 3 differ only in their time, build and refresh fields: `atlas_status` (1), `ref_diff` (1), `repo_map` (1)" in text


def test_an_answer_that_differs_in_more_than_time_is_flagged_for_judgment_at_the_source(tmp_path):
    text, _ = run(make(tmp_path, golden_differ=(("q2_other_label", False),)))
    assert "1 differ in more: judge them at the source" in text
    assert "| Q2 `http_map` | ⚠ differs: judge it at the source |" in text


def test_the_table_has_a_row_per_question_and_marks_the_time_fields(tmp_path):
    text, _ = run(make(tmp_path, golden_differ=(("q5_ref_diff", True),)))
    assert "| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |" in text
    assert "| Q3 map | ✅ the same on the 3 tenants |" in text and "| Q5 `ref_diff` | ✅ the same but its time fields |" in text


def test_a_run_that_failed_and_a_snapshot_with_the_old_build_are_said(tmp_path):
    text, _ = run(make(tmp_path, failed=True, stale=True))
    assert "1 not ok (2 of 3)" in text or "1 not ok (3 of 3)" in text
    assert "3 still hold the old build" in text


def test_the_two_sentences_the_author_writes_are_marked_when_missing(tmp_path):
    text, _ = run(make(tmp_path), what="", merge="")
    assert "**TODO: one sentence, what PR #85 changed**" in text and "(`<the merge>`," in text
    assert text.rstrip().endswith("**What the round shows.** **TODO: what the numbers say, in the author's words.**")


def test_the_graph_after_and_the_graph_before_are_each_told_by_their_own_file(tmp_path):
    text, history = run(make(tmp_path, mismatch_after=2, symbols=(100, 103)))
    assert "held `main`'s dry-run on every snapshot (0 mismatching)" in text
    assert "The graph after holds the branch's dry-run on every snapshot (2 mismatching)" in text
    assert "(2 mismatching): 103 symbols" in history


def test_the_history_line_has_the_pr_the_round_the_picture_and_the_calls(tmp_path):
    _, history = run(make(tmp_path, golden_differ=(("atlas_status", True),)))
    assert history.startswith("- 2026-11-08: PR #85 is validated on a live install (the forty-third round).")
    assert "identical in all 3 snapshots" in history and "(0 mismatching): 100 symbols, 500 `CALLS`" in history
    assert "of the 7 calls, 6 are the same and 1 differ only in their time, build and refresh fields." in history


@pytest.mark.parametrize("n,word", [(1, "first"), (2, "second"), (9, "ninth"), (12, "twelfth"), (19, "nineteenth"), (20, "twentieth"), (21, "twenty-first"),
                                    (30, "thirtieth"), (43, "forty-third"), (44, "forty-fourth"), (50, "fiftieth"), (99, "ninety-ninth")])
def test_the_round_number_is_written_in_words(n, word):
    assert draft.ordinal(n) == word


def test_nothing_the_live_data_names_reaches_the_output(tmp_path, capsys):
    d = make(tmp_path, dry=("identical", "differs", "identical"), golden_differ=(("atlas_status", True), ("secret_label", False), ("q1_secret_label", False)),
             failed=True, stale=True)
    assert draft.main([str(d), "--pr", "85", "--number", "43", "--date", "2026-11-08"]) == 0
    out = capsys.readouterr().out
    assert out.count("\n---\n") == 1
    for name in SECRETS:
        assert name not in out, name


def test_without_the_folder_or_the_flags_it_prints_its_usage_and_ends_with_2(tmp_path, capsys):
    assert draft.main([]) == 2
    assert draft.main([str(tmp_path / "nowhere"), "--pr", "85", "--number", "43", "--date", "2026-11-08"]) == 2
    assert draft.main([str(tmp_path), "--pr", "85"]) == 2
    assert draft.main([str(make(tmp_path)), "--pr", "x", "--number", "43", "--date", "2026-11-08"]) == 2
    assert draft.main([str(make(tmp_path / "c")), "--pr", "85", "--number", "43", "--date", "yesterday"]) == 2
    assert "round.py INFLIGHT --pr N --number K" in capsys.readouterr().err
