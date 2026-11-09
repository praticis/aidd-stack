"""The research round's orchestration (scripts/review/research-round.js), with simulated agents.

What the script must do itself: cap the researchers, give each its mode, its stop rule and its limits, carry a silent
researcher as missing and not as evidence, hand the synthesis every report and the challenger the synthesis and the
reports, pass each stage its effort, and refuse to start without what it needs."""
import json
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "review" / "research-round.js"
HARNESS = HERE / "research_harness.mjs"


@pytest.fixture(scope="module")
def out():
    done = subprocess.run(["node", str(HARNESS), str(SCRIPT)], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def labels(run):
    return [c["label"] for c in run["calls"]]


def prompt(run, label):
    return next(c["prompt"] for c in run["calls"] if c["label"] == label)


def test_one_researcher_per_question_then_a_synthesis_then_a_challenge(out):
    run = out["full"]
    assert labels(run) == ["research:a", "research:b", "research:c", "synthesis", "challenge"]
    assert [r["id"] for r in run["result"]["reports"]] == ["a", "b", "c"] and run["result"]["missing"] == []
    assert run["result"]["synthesis"]["decision"] == "amend-plan" and run["result"]["challenge"]["verdict"] == "weakened"


def test_each_researcher_gets_its_question_the_plan_the_context_and_the_hard_limits(out):
    for label in ("research:a", "research:b", "research:c"):
        text = prompt(out["full"], label)
        assert f"PROMPT-{label.split(':')[1]}" in text and "/r/plan.md" in text and "/r/parent.md" in text
        assert "TOOLS-HERE" in text and "untrusted data" in text and "READ-ONLY" in text and "never run it" in text


def test_the_mode_of_a_question_changes_what_the_researcher_may_do(out):
    run = out["full"]
    assert "Mode: web" in prompt(run, "research:a") and "Mode: measure" in prompt(run, "research:b")
    assert "Mode: read" in prompt(run, "research:c")


def test_the_stop_rule_is_a_tool_call_budget_per_question_with_a_default_of_sixty(out):
    run = out["full"]
    assert "at most 20 tool calls" in prompt(run, "research:b") and "at most 60 tool calls" in prompt(run, "research:a")


def test_docker_is_off_unless_the_arguments_allow_it(out):
    assert "You may run containers" in prompt(out["full"], "research:a")
    assert "Use no Docker" in prompt(out["plain"], "research:a")


def test_the_synthesis_gets_every_report_and_the_rules_and_the_challenger_gets_the_synthesis_too(out):
    run = out["full"]
    synthesis = prompt(run, "synthesis")
    assert all(f"answer {i}" in synthesis for i in "abc") and "'not verified'" in synthesis
    assert "a refactor PR must change nothing" in synthesis
    challenge = prompt(run, "challenge")
    assert "SYNTH-RATIONALE" in challenge and all(f"answer {i}" in challenge for i in "abc")


def test_the_rules_argument_replaces_the_default_rules(out):
    text = prompt(out["customRules"], "synthesis")
    assert "CUSTOM-RULES" in text and "a refactor PR must change nothing" not in text


def test_a_silent_researcher_is_missing_not_evidence_and_does_not_stop_the_round(out):
    run = out["silent"]
    assert run["result"]["missing"] == ["b"]
    assert {"id": "b", "missing": True} in run["result"]["reports"]
    assert "returned nothing and are not evidence either way: b" in prompt(run, "synthesis")
    assert "reports back: 1/2; missing: b" in run["logs"]
    assert labels(run) == ["research:a", "research:b", "synthesis", "challenge"]


def test_synthesize_false_stops_after_the_reports(out):
    run = out["reportsOnly"]
    assert labels(run) == ["research:a"] and run["result"]["synthesis"] is None and run["result"]["challenge"] is None


def test_challenge_false_stops_after_the_synthesis(out):
    run = out["noChallenge"]
    assert labels(run) == ["research:a", "synthesis"] and run["result"]["challenge"] is None


def test_the_efforts_default_to_medium_high_high_and_can_be_set(out):
    assert [c["effort"] for c in out["plain"]["calls"]] == ["medium", "high", "high"]
    assert [c["effort"] for c in out["efforts"]["calls"]] == ["low", "medium", "xhigh"]


def test_four_questions_are_the_cap_and_allow_more_lifts_it(out):
    assert len([c for c in out["five"]["calls"] if c["phase"] == "Research"]) == 5
    assert out["tooMany"].startswith("research-round: at most 4 questions")


def test_the_script_refuses_to_start_without_what_it_needs(out):
    assert out["noRepo"] == "research-round: args.repo is required"
    assert out["noPlan"] == "research-round: args.plan is required"
    assert out["noQuestions"] == "research-round: args.questions is a non-empty list of { id, prompt }"
    assert out["noPrompt"] == 'research-round: question "a" needs an id and a prompt'
    assert out["dupId"] == 'research-round: two questions have the id "a"'
    assert out["badKind"] == 'research-round: question "a" has kind "guess": read, measure or web'


def test_the_script_names_itself_research_round():
    assert 'name: \'research-round\'' in SCRIPT.read_text()
