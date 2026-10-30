"""Where a Python import's module is. An absolute import is looked for under the directory above the importing file's
top package, then the root of the file's module, the repo's root and `src/`, and the first root that has the module
decides, whatever the process's hash seed. Where a case says which file CPython loads, CPython runs it."""

import os
import subprocess
import sys
from pathlib import Path

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
PROJECT = {
    "pyproject.toml": '[project]\nname = "site"\n',
    "shop/models.py": MODELS,
    "project/manage.py": "import sys\nimport shop.views\nprint(sys.modules['shop.models'].__file__)\n",
    "project/shop/__init__.py": "",
    "project/shop/models.py": MODELS,
    "project/shop/views.py": "from shop.models import B\n",
}
NAMESPACE = {
    "pkg/__init__.py": "",
    "pkg/ns/json.py": "import json\nprint(json.__file__)\n",
}


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)


def _resolved(root: Path) -> set[str]:
    ran = subprocess.run([sys.executable, "-c", RESOLVE, str(root)], capture_output=True, text=True, check=True)
    return set(ran.stdout.splitlines())


def _loaded(root: Path, *args: str) -> str:
    """The file CPython prints, run from the case's root, relative to it; `outside` for one out of it."""
    ran = subprocess.run([sys.executable, "-B", *args], cwd=root, capture_output=True, text=True, check=True)
    path, base = Path(ran.stdout.strip()).resolve(), root.resolve()
    return str(path.relative_to(base)) if path.is_relative_to(base) else "outside"


def test_an_absolute_import_resolves_to_the_same_module_whatever_the_hash_seed(tmp_path):
    _write(tmp_path, FILES)
    runs = [subprocess.Popen([sys.executable, "-c", RESOLVE, str(tmp_path)], stdout=subprocess.PIPE, text=True,
                             env={**os.environ, "PYTHONHASHSEED": str(seed)}) for seed in SEEDS]
    answers = {p.communicate()[0] for p in runs}
    assert all(p.returncode == 0 for p in runs)
    assert answers == {"services/api/app/use.py app.models services/api/app/models.py\n"
                       "tools/run.py app.models app/models.py\n"}


def test_an_absolute_import_is_found_where_its_package_runs_from(tmp_path):
    _write(tmp_path, PROJECT)
    loaded = _loaded(tmp_path, "project/manage.py")
    assert loaded == "project/shop/models.py"
    assert {"project/manage.py shop.views project/shop/views.py",
            f"project/shop/views.py shop.models {loaded}"} <= _resolved(tmp_path)


def test_a_directory_inside_a_package_is_no_root_of_its_imports(tmp_path):
    _write(tmp_path, NAMESPACE)
    assert _loaded(tmp_path, "-c", "import pkg.ns.json") == "outside"
    assert not any(line.startswith("pkg/ns/json.py json pkg/") for line in _resolved(tmp_path))
