"""The shape ratchet (scripts/shape.py `--against`): what is over a target may stay while it does not grow, nothing new
joins it, and a function that only moved to another file is the same function."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import shape  # noqa: E402


def fn(file, name, complexity, line=1):
    return {"file": file, "line": line, "function": name, "complexity": complexity}


def test_a_function_that_stays_as_it_was_passes():
    assert shape.worse_functions([fn("a.py", "run", 12)], [fn("a.py", "run", 12, line=40)]) == []


def test_a_function_that_grows_fails():
    assert shape.worse_functions([fn("a.py", "run", 12)], [fn("a.py", "run", 13)]) == ["a.py:1 run: complexity 13, was 12"]


def test_a_function_new_over_the_limit_fails():
    assert shape.worse_functions([], [fn("b.py", "scan", 10)]) == ["b.py:1 scan: complexity 10, new over the limit"]


def test_a_function_moved_to_another_file_is_the_same_function():
    assert shape.worse_functions([fn("a.py", "compose", 16)], [fn("pkg/compose.py", "compose", 16)]) == []
    assert shape.worse_functions([fn("a.py", "compose", 16)], [fn("pkg/compose.py", "compose", 17)]) == \
        ["pkg/compose.py:1 compose: complexity 17, was 16"]


def test_of_two_functions_with_one_name_the_one_that_grew_shows():
    base = [fn("a.py", "run", 12), fn("a.py", "run", 10)]
    head = [fn("a.py", "run", 12), fn("a.py", "run", 11, line=90)]
    assert shape.worse_functions(base, head) == ["a.py:90 run: complexity 11, was 10"]


def test_a_function_brought_under_the_limit_leaves_room_for_no_other():
    assert shape.worse_functions([fn("a.py", "run", 12)], [fn("a.py", "other", 10)]) == \
        ["a.py:1 other: complexity 10, new over the limit"]


def test_modules():
    base = [{"file": "a.py", "lines": 760}]
    assert shape.worse_modules(base, [{"file": "a.py", "lines": 700}]) == []
    assert shape.worse_modules(base, [{"file": "a.py", "lines": 761}]) == ["a.py: 761 lines, was 760"]
    assert shape.worse_modules(base, [{"file": "b.py", "lines": 301}]) == ["b.py: 301 lines, new over the limit"]
