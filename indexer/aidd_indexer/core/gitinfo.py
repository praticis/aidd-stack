"""Read-only git facts about the repo being indexed."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def is_git_repo(repo: Path) -> bool:
    return _git(repo, "rev-parse", "--is-inside-work-tree") == "true"


def head_sha(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD") or "workdir"


def current_ref(repo: Path) -> str:
    ref = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    return ref if ref and ref != "HEAD" else "detached"


def default_ref(repo: Path) -> str:
    sym = _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if sym:
        return sym.split("/", 1)[-1]
    for cand in ("main", "master", "develop"):
        if _git(repo, "rev-parse", "--verify", "--quiet", cand) is not None:
            return cand
    return current_ref(repo)


def remote_url(repo: Path) -> str:
    return _git(repo, "remote", "get-url", "origin") or ""


def tracked_files(repo: Path) -> list[str] | None:
    """Files git knows about (respects .gitignore). None when not a git repo."""
    out = _git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if out is None:
        return None
    return [p for p in out.split("\0") if p]


# -- refs & export (used by the ref policy and the worktree-free indexing) -----------

def list_branches(repo: Path) -> list[dict]:
    """Remote-tracking branches (origin/*) when present, else local heads.
    Each: {name, sha, committed_at (ISO), remote (bool)}."""
    fmt = "%(refname:short)%00%(objectname)%00%(committerdate:iso8601-strict)"
    out = _git(repo, "for-each-ref", "--sort=-committerdate", f"--format={fmt}", "refs/remotes/origin", "refs/heads")
    if not out:
        return []
    remote: list[dict] = []
    local: list[dict] = []
    for line in out.splitlines():
        parts = line.split("\0")
        if len(parts) != 3:
            continue
        name, sha, date = parts
        if name.startswith("origin/"):
            short = name[len("origin/"):]
            if short == "HEAD":
                continue
            remote.append({"name": short, "sha": sha, "committed_at": date, "remote": True})
        else:
            local.append({"name": name, "sha": sha, "committed_at": date, "remote": False})
    return remote if remote else local


def is_merged_into(repo: Path, sha: str, base_sha: str) -> bool:
    return _git(repo, "merge-base", "--is-ancestor", sha, base_sha) is not None


def export_tree(repo: Path, sha: str, dest: Path) -> bool:
    """Materialize a commit into `dest` with `git archive` — works on a read-only
    mount and leaves no trace in the repo (unlike `git worktree`)."""
    dest.mkdir(parents=True, exist_ok=True)
    try:
        archive = subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", str(repo), "archive", "--format=tar", sha],
            capture_output=True, timeout=600, check=False,
        )
        if archive.returncode != 0:
            return False
        tar = subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, capture_output=True, timeout=600, check=False)
        return tar.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def fetch(repo: Path, timeout: int = 120) -> tuple[bool, str]:
    """`git fetch --all --prune` so origin/* reflects the remote before planning.
    Never raises: returns (ok, message) — a failure means we plan on local refs."""
    try:
        out = subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", str(repo), "fetch", "--all", "--prune", "--quiet"],
            capture_output=True, text=True, timeout=timeout, check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},   # never hang on a credential prompt
        )
    except FileNotFoundError:
        return False, "git not found"
    except subprocess.TimeoutExpired:
        return False, f"fetch timed out after {timeout}s"
    if out.returncode != 0:
        lines = [l.strip() for l in (out.stderr or out.stdout).strip().splitlines() if l.strip()]
        # prefer the line that names the cause over git's generic trailer
        cause = next((l for l in lines if any(k in l for k in ("Permission denied", "Could not resolve", "unable to fork",
                                                                   "Authentication failed", "terminal prompts disabled",
                                                                   "Host key verification", "timed out"))), None)
        return False, (cause or (lines[-1] if lines else f"exit {out.returncode}"))
    return True, "ok"
