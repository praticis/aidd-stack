"""Builds a small repo from a JSON dict of files and prints the CALLS edges out of the symbols whose qualified name ends
in SUFFIX (default `Run`).   probe.py FILES.json [SUFFIX]"""
import contextlib, io, json, sys, tempfile
from pathlib import Path

from aidd_indexer.cli import extract_and_resolve
from aidd_indexer.core.model import RepoInfo

files = json.load(open(sys.argv[1]))
suffix = sys.argv[2] if len(sys.argv) > 2 else "Run"
root = Path(tempfile.mkdtemp())
for rel, text in files.items():
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text)
with contextlib.redirect_stderr(io.StringIO()):
    res, rv = extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)))
names = {s.id: s.qualified_name for s in res.symbols}
for c in rv.calls:
    if names.get(c.caller_id, "").endswith(suffix):
        print(names[c.caller_id], "->", names.get(c.callee_id, c.callee_id), c.strategy)
