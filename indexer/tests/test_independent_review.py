"""The independent reviewer's orchestration (scripts/review/independent-review.js), with simulated agents.

The script asks agents; what it must do itself is pool their objections, merge the ones about one place to the worse
severity, send only the right ones to a second reader, pass each agent its effort and keep what the author wrote out
of a diff review. The harness plays the agents and prints what the script asked and returned."""
import json
import re
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "review" / "independent-review.js"
HARNESS = HERE / "review_harness.mjs"

@pytest.fixture(scope="module")
def out():
    done = subprocess.run(["node", str(HARNESS), str(SCRIPT)], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def labels(run, phase=None):
    return [c["label"] for c in run["calls"] if phase is None or c["phase"] == phase]


def of_phase(run, phase):
    return [c for c in run["calls"] if c["phase"] == phase]


def test_a_plan_has_one_challenger_and_only_its_blocking_objection_is_rechecked(out):
    run = out["plan"]
    assert labels(run) == ["review:challenge", "verify:x.py:1"]
    first, minor = run["result"]["objections"]
    assert first["verification"] == {"confirmed": True, "how": "saw it"}
    assert "verification" not in minor
    assert run["result"]["not_rechecked"] == []
    assert run["result"]["verdicts"] == [
        {"lens": "challenge", "verdict": "weakened", "would_change_my_mind": ["w"], "not_checked": []}]


def test_a_plan_review_names_the_plan_the_text_to_refute_and_the_data(out):
    prompt = of_phase(out["plan"], "Review")[0]["prompt"]
    assert "/r/plan.md" in prompt and "text you are to refute: /r/synth.md" in prompt and "/d/a.json" in prompt


def test_objections_about_one_place_merge_to_the_worse_severity_and_keep_both_lenses(out):
    objections = out["diff"]["result"]["objections"]
    assert [(o["where"], o["severity"], o["lenses"]) for o in objections] == [
        ("a.py:10", "blocking", ["correctness", "rules"]),
        ("b.md:3", "significant", ["rules"])]
    assert objections[0]["point"] == "module too long"


def test_the_worse_severity_wins_whichever_lens_reports_first_and_a_tie_keeps_the_first(out):
    by_place = {o["where"]: o for o in out["mergeOrder"]["result"]["objections"]}
    assert (by_place["m.py:1"]["severity"], by_place["m.py:1"]["point"]) == ("blocking", "first, blocking")
    assert by_place["n.py:2"]["point"] == "tie, first" and by_place["n.py:2"]["lenses"] == ["correctness", "rules"]


def test_a_merge_keeps_the_text_of_the_lesser_objection_under_also(out):
    by_place = {o["where"]: o for o in out["mergeOrder"]["result"]["objections"]}
    assert [(a["lens"], a["severity"], a["point"]) for a in by_place["m.py:1"]["also"]] == [("rules", "significant", "later, significant")]
    assert [a["point"] for a in by_place["n.py:2"]["also"]] == ["tie, second"]
    assert by_place["s.py:3"]["also"] == [], "the same text from two lenses is one objection"
    merged = out["diff"]["result"]["objections"][0]
    assert [(a["lens"], a["point"]) for a in merged["also"]] == [("correctness", "wrong cond")]
    assert out["diff"]["result"]["objections"][1]["also"] == []


def test_max_verify_zero_rechecks_nothing_and_names_what_was_left(out):
    run = out["maxVerifyZero"]
    assert labels(run, "Verify") == [] and run["result"]["not_rechecked"] == ["a.py:10"]


def test_an_objection_with_no_where_is_rechecked_by_its_point_and_does_not_crash(out):
    run = out["emptyWhere"]
    assert labels(run, "Verify") == ["verify:no pointer given"]
    assert run["result"]["objections"][0]["verification"]["confirmed"] is False


def test_a_lens_that_returns_nothing_is_logged_and_does_not_stop_the_others(out):
    run = out["diff"]
    verdicts = {v["lens"]: v["verdict"] for v in run["result"]["verdicts"]}
    assert verdicts == {"correctness": "weakened", "rules": "refuted", "losses": None}
    assert "lens losses returned nothing" in run["logs"]


def test_max_verify_cuts_the_second_readers_and_names_what_was_left(out):
    run = out["diff"]
    assert labels(run, "Verify") == ["verify:a.py:10"]
    assert run["result"]["not_rechecked"] == ["b.md:3"]
    assert run["result"]["objections"][0]["verification"] == {"confirmed": False, "how": "did not reproduce"}
    assert any("not re-checked" in line and "b.md:3" in line for line in run["logs"])


def test_the_efforts_reach_the_lenses_and_the_second_reader(out):
    run = out["diff"]
    assert {c["effort"] for c in of_phase(run, "Review")} == {"low"}
    assert {c["effort"] for c in of_phase(run, "Verify")} == {"high"}


def test_the_default_efforts_are_medium_for_the_lenses_and_xhigh_for_the_second_reader(out):
    run = out["diffDefaults"]
    assert {c["effort"] for c in of_phase(run, "Review")} == {"medium"}
    assert {c["effort"] for c in of_phase(run, "Verify")} == {"xhigh"}


def test_by_default_only_a_blocking_objection_gets_a_second_reader(out):
    assert labels(out["diffDefaults"], "Verify") == ["verify:a.py:10"]
    assert out["diffDefaults"]["result"]["not_rechecked"] == []


def test_verify_all_rechecks_every_objection_but_the_minor_ones(out):
    run = out["verifyAll"]
    assert labels(run, "Verify") == ["verify:a.py:10", "verify:b.md:3"]
    minor = [o for o in run["result"]["objections"] if o["severity"] == "minor"]
    assert [o["where"] for o in minor] == ["c.py:1"] and "verification" not in minor[0]


def test_verify_none_asks_no_second_reader(out):
    run = out["verifyNone"]
    assert labels(run, "Verify") == []
    assert all("verification" not in o for o in run["result"]["objections"])


def test_a_second_reader_that_returns_nothing_leaves_the_objection_unconfirmed_not_dropped(out):
    objections = out["verifierSilent"]["result"]["objections"]
    assert objections[0]["verification"] == {"confirmed": None, "how": "the verifier returned nothing"}


def test_a_review_that_finds_nothing_returns_holds_and_an_empty_list(out):
    run = out["holds"]
    assert run["result"]["objections"] == [] and labels(run, "Verify") == []
    assert {v["verdict"] for v in run["result"]["verdicts"]} == {"holds"}


def test_a_diff_has_three_default_lenses_and_the_lenses_argument_replaces_them(out):
    assert labels(out["diffDefaults"], "Review") == ["review:correctness", "review:rules", "review:losses"]
    run = out["customLenses"]
    assert labels(run, "Review") == ["review:only"] and "FOCUS-TEXT" in run["calls"][0]["prompt"]


def test_the_rules_argument_replaces_the_rules_lens_default(out):
    prompts = {c["label"]: c["prompt"] for c in out["customRules"]["calls"]}
    assert "CUSTOM-RULES" in prompts["review:rules"] and "Complexity <= 9" not in prompts["review:rules"]
    assert "Complexity <= 9" in out["diffDefaults"]["calls"][1]["prompt"]


def test_every_prompt_keeps_the_hard_limits_and_the_diff_review_does_not_show_the_authors_text(out):
    for call in out["diffDefaults"]["calls"]:
        assert "untrusted data" in call["prompt"] and "Read-only" in call["prompt"]
    review = of_phase(out["diffDefaults"], "Review")[0]["prompt"]
    assert "git -C /r diff main...HEAD" in review and "text you are to refute" not in review
    second = of_phase(out["diffDefaults"], "Verify")[0]["prompt"]
    assert "module too long" in second and "a.py:10" in second and "REPRODUCE" in second


def test_the_script_refuses_to_start_without_what_it_needs(out):
    assert out["missingKind"] == "independent-review: args.kind is required"
    assert out["missingRepo"] == "independent-review: args.repo is required"
    assert out["missingTarget"] == "independent-review: args.target is required"
    assert out["badKind"] == 'independent-review: args.kind is "plan" or "diff"'


def test_the_script_names_itself_independent_review():
    assert re.search(r"^export const meta = \{\s*name: 'independent-review',", SCRIPT.read_text(), re.M)
