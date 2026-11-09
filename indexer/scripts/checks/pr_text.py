#!/usr/bin/env python3
"""Refuses a line of a pull request's title, body or commit messages that the project's rules keep out of them.

The rules are a list, `pr_text_deny.txt` beside this file: one per line, `id :: regex :: reason`; a line that starts with `#`
is a comment. A regex is searched in each line of each text, case-insensitively. A hit names the text (the title, the body or
a commit), the line, the rule and its reason. Nothing is fetched here: it reads only the text it is given.

    python3 -I indexer/scripts/checks/pr_text.py [--title-file F] [--body-file F] [--rules F]
                                                 (--commits-json F | --base REF --head REF)

`--commits-json` is the output of `gh api repos/R/pulls/N/commits --paginate --slurp` (a list of pages), or a list of commit
objects; `--base` and `--head` read the messages from git instead. The title and the body are files, so that text nobody
trusts never reaches a shell. Exit 0 with no hit, 1 with a hit, 2 when the rules file is wrong. Markdown on stdout, for the job
summary.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

RULES_FILE = Path(__file__).with_name("pr_text_deny.txt")
SEPARATOR = " :: "


class Rule(NamedTuple):
    id: str
    regex: re.Pattern
    reason: str


class Hit(NamedTuple):
    where: str
    line: int
    rule: Rule
    text: str


def load_rules(text: str) -> list[Rule]:
    rules: list[Rule] = []
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        parts = [p.strip() for p in raw.split(SEPARATOR, 2)]
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"line {n}: expected `id :: regex :: reason`")
        name, pattern, reason = parts
        if any(r.id == name for r in rules):
            raise ValueError(f"line {n}: the id {name!r} is already a rule")
        try:
            rules.append(Rule(name, re.compile(pattern, re.IGNORECASE), reason))
        except re.error as error:
            raise ValueError(f"line {n}: the regex of {name!r} is wrong: {error}") from error
    return rules


def scan(texts: list[tuple[str, str]], rules: list[Rule]) -> list[Hit]:
    hits: list[Hit] = []
    for where, text in texts:
        for n, line in enumerate(text.splitlines(), 1):
            hits += [Hit(where, n, rule, line.strip()) for rule in rules if rule.regex.search(line)]
    return hits


def commit_texts(data: list) -> list[tuple[str, str]]:
    """`(where, message)` of each commit, from a list of commit objects or of pages of them."""
    out = []
    for item in data:
        for commit in item if isinstance(item, list) else [item]:
            out.append((f"commit {commit['sha'][:7]}", commit["commit"]["message"]))
    return out


def git_texts(base: str, head: str) -> list[tuple[str, str]]:
    raw = subprocess.run(["git", "log", "-z", "--format=%h%n%B", f"{base}..{head}"],
                         capture_output=True, text=True, check=True).stdout
    out = []
    for record in raw.split("\0"):
        if record.strip():
            sha, _, message = record.partition("\n")
            out.append((f"commit {sha.strip()}", message))
    return out


def report(hits: list[Hit], commits: int) -> str:
    head = "### Pull request text\n\n"
    if not hits:
        return head + f"No rule of `pr_text_deny.txt` matches the title, the body or the {commits} commit message(s).\n"
    lines = [f"- {h.where}, line {h.line}: `{h.text[:100].replace('`', chr(39))}`: {h.rule.id}, {h.rule.reason}" for h in hits]
    return (head + f"{len(hits)} line(s) that the project's rules keep out of a pull request:\n\n" + "\n".join(lines)
            + "\n\nRemove them: edit the body and re-run this job, or amend the commit and push. The rules are in "
              "`indexer/scripts/checks/pr_text_deny.txt`.\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--title-file", type=Path)
    p.add_argument("--body-file", type=Path)
    p.add_argument("--rules", type=Path, default=RULES_FILE)
    p.add_argument("--commits-json", type=Path)
    p.add_argument("--base")
    p.add_argument("--head")
    a = p.parse_args(argv)
    try:
        rules = load_rules(a.rules.read_text())
    except ValueError as error:
        print(f"{a.rules}: {error}", file=sys.stderr)
        return 2
    texts = [(name, f.read_text()) for name, f in (("the title", a.title_file), ("the body", a.body_file)) if f]
    commits = commit_texts(json.loads(a.commits_json.read_text())) if a.commits_json else []
    if a.base and a.head:
        commits += git_texts(a.base, a.head)
    hits = scan(texts + commits, rules)
    print(report(hits, len(commits)))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
