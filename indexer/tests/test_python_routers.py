"""The HTTP scanner's questions to Python's scopes and types: which router a name refers to where a route is registered,
and which function or method a router is handed to. The routes a case names are the ones CPython registers: each case
runs with a router that composes prefixes as FastAPI's does, outside the case's repo, and its routes are compared with
the case's."""

import contextlib
import io
import subprocess
import sys

import pytest

from aidd_indexer.cli import extract_and_resolve
from aidd_indexer.core.model import RepoInfo

FASTAPI = """class APIRouter:
    def __init__(self, prefix=""):
        self.prefix, self.routes = prefix, []
    def get(self, path):
        def register(f):
            self.routes.append(("GET", self.prefix + path))
            return f
        return register
    def include_router(self, router, prefix=""):
        self.routes += [(m, self.prefix + prefix + p) for m, p in router.routes]
class FastAPI(APIRouter):
    pass
"""
RUN = "import app.main\nprint(sorted(app.main.app.routes))\n"
MAIN = ('from fastapi import APIRouter, FastAPI\n%s\napp = FastAPI()\nv1 = APIRouter(prefix="/api")\n%s\n'
        'app.include_router(v1)\n')
REGISTER = 'from fastapi import APIRouter\ndef register(router: APIRouter):\n    @router.get("/users")\n' \
           '    def list_users(): return []\n'
ROUTER_CLASS = 'from fastapi import APIRouter\nclass VersionedRouter(%s):\n    pass\n'
CLASS_MAIN = ('from fastapi import FastAPI\nfrom app.routes import %s\napp = FastAPI()\nv1 = %s(prefix="/api")\n'
              '@v1.get("/users")\ndef list_users(): return []\napp.include_router(v1)\n')
API_USERS, ROOT = {("GET", "/api/users")}, {("GET", "/")}

ROUTES = {
    "a-repo-router-class": {
        "app/routes.py": ROUTER_CLASS % "APIRouter",
        "app/main.py": CLASS_MAIN % ("VersionedRouter", "VersionedRouter")},
    "a-repo-router-class-under-an-alias": {
        "app/routes.py": ROUTER_CLASS % "APIRouter",
        "app/main.py": CLASS_MAIN % ("VersionedRouter as Versioned", "Versioned")},
    "a-repo-router-class-over-a-base-of-another-package": {
        "app/base/routers.py": "from fastapi import APIRouter\nclass BaseRouter(APIRouter):\n    pass\n",
        "app/routes.py": "from app.base.routers import BaseRouter\nclass VersionedRouter(BaseRouter):\n    pass\n",
        "app/main.py": CLASS_MAIN % ("VersionedRouter", "VersionedRouter")},
    "an-annotated-router-parameter": {
        "app/routes.py": REGISTER,
        "app/main.py": MAIN % ("from app.routes import register", "register(v1)")},
}
SCOPED = {
    "a-router-a-function-binds-as-global": {
        "app/main.py": 'from fastapi import APIRouter, FastAPI\napp = FastAPI()\ndef setup():\n    global v1\n'
                       '    v1 = APIRouter(prefix="/api")\nsetup()\n@v1.get("/users")\ndef list_users(): return []\n'
                       "app.include_router(v1)\n"},
    "a-class-body-does-not-enclose-its-methods": {
        "app/main.py": MAIN % ("", 'class Routes:\n    v1 = APIRouter(prefix="/other")\n    def register(self):\n'
                                   '        @v1.get("/users")\n        def list_users(): return []\nRoutes().register()')},
}
APPLICATION = {
    "an-application-a-function-binds-as-global": {
        "app/main.py": 'from fastapi import FastAPI\ndef create():\n    global app\n    app = FastAPI()\ncreate()\n'
                       '@app.get("/")\ndef root(): return {}\n'},
}
TYPED = {
    "a-router-handed-to-a-method-of-a-typed-value": {
        "app/routes.py": 'from fastapi import APIRouter\nclass Users:\n    def register(self, router: APIRouter):\n'
                         '        @router.get("/users")\n        def list_users(): return []\n',
        "app/main.py": MAIN % ("from app.routes import Users", "users = Users()\nusers.register(v1)")},
    "a-router-handed-to-a-function-of-an-imported-module": {
        "app/routes.py": REGISTER,
        "app/main.py": MAIN % ("from app import routes", "routes.register(v1)")},
}
CLASSES = {
    "a-router-class-a-function-imports": {
        "app/routes.py": ROUTER_CLASS % "APIRouter",
        "app/main.py": 'from fastapi import FastAPI\napp = FastAPI()\ndef build():\n'
                       '    from app.routes import VersionedRouter\n    v1 = VersionedRouter(prefix="/api")\n'
                       '    @v1.get("/users")\n    def list_users(): return []\n    app.include_router(v1)\nbuild()\n'},
    "a-repo-router-class-whose-base-has-a-homonym": {
        "app/base/routers.py": "from fastapi import APIRouter\nclass BaseRouter(APIRouter):\n    pass\n",
        "app/other/routers.py": "class Mixin:\n    pass\nclass BaseRouter(Mixin):\n    pass\n",
        "app/routes.py": "from app.base.routers import BaseRouter\nclass VersionedRouter(BaseRouter):\n    pass\n",
        "app/main.py": CLASS_MAIN % ("VersionedRouter", "VersionedRouter")},
}


def _cases(cases: dict, routes: set = API_USERS) -> list:
    return [pytest.param(files, routes, id=i) for i, files in cases.items()]


CASES = _cases(ROUTES) + _cases(SCOPED) + _cases(APPLICATION, ROOT) + _cases(TYPED) + _cases(CLASSES)


def _repo(root, files: dict[str, str]):
    for rel, body in {"pyproject.toml": '[project]\nname = "app"\n', "app/__init__.py": "", **files}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    return root


@pytest.mark.parametrize("files, routes", [pytest.param(*p.values, id=p.id) for p in CASES])
def test_cpython_registers_the_routes_the_case_names(tmp_path, files, routes):
    (tmp_path / "framework").mkdir()
    (tmp_path / "framework" / "fastapi.py").write_text(FASTAPI)
    repo = _repo(tmp_path / "repo", files)
    ran = subprocess.run([sys.executable, "-c", f"import sys; sys.path[:0] = ['{tmp_path / 'framework'}']\n{RUN}"],
                         cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    assert ran == str(sorted(routes))


@pytest.mark.parametrize("files, routes", CASES)
def test_a_routers_prefix_reaches_its_routes(tmp_path, files, routes):
    repo = RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(_repo(tmp_path, files)))
    with contextlib.redirect_stderr(io.StringIO()):
        res, _ = extract_and_resolve(repo)
    assert {(e.method, e.path) for e in res.endpoints} == routes
