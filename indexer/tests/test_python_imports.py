"""Where a Python import's module is. An absolute import is looked for under the root of the importing file's module,
then the repo's root, then `src/`, and the first root that has the module decides, whatever the process's hash seed."""

import os
import subprocess
import sys

MODELS = "class B: pass\n"
FILES = {
    "services/api/pyproject.toml": '[project]\nname = "api"\n',
    "services/api/app/models.py": MODELS,
    "services/api/app/use.py": "from app.models import B\n",
    "app/models.py": MODELS,
    "src/app/models.py": MODELS,
    "tools/run.py": "from app.models import B\n",
}
RESOLVE = """import contextlib, io, sys
from aidd_indexer.cli import extract_and_resolve
from aidd_indexer.core.model import RepoInfo
with contextlib.redirect_stderr(io.StringIO()):
    res, rv = extract_and_resolve(RepoInfo(tenant="t", name="r", ref="main", commit_sha="x", root=sys.argv[1]), [])
path = {f.id: f.path for f in res.files}
for e in sorted(rv.imports, key=lambda e: path[e.file_id]):
    print(path[e.file_id], e.spec, path.get(e.target_id, e.target_label))
"""
SEEDS = range(8)


def test_an_absolute_import_resolves_to_the_same_module_whatever_the_hash_seed(tmp_path):
    for rel, text in FILES.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    runs = [subprocess.Popen([sys.executable, "-c", RESOLVE, str(tmp_path)], stdout=subprocess.PIPE, text=True,
                             env={**os.environ, "PYTHONHASHSEED": str(seed)}) for seed in SEEDS]
    answers = {p.communicate()[0] for p in runs}
    assert all(p.returncode == 0 for p in runs)
    assert answers == {"services/api/app/use.py app.models services/api/app/models.py\n"
                       "tools/run.py app.models app/models.py\n"}
