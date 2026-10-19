"""`path_of` case by case, through the extraction of a small repository: one outbound call per line, so a broken rule
fails the case that names it instead of a whole fixture."""

import contextlib
import io

import pytest

FILES = {
    "web/package.json": '{"name": "web"}',
    "web/src/client.ts": """import axios from 'axios';
const BASE = '/api/v1';
const USERS = BASE + '/users';
export function calls(id: string, q: string, flag: boolean) {
  axios.get('/plain');
  axios.get(`/items/${id}`);
  axios.get(USERS);
  axios.get(`${BASE}/orders/${id}`);
  axios.get('/search' + (flag ? '?all=1' : ''));
  axios.get(`/stats${buildQuery(q)}`);
  axios.get(process.env.API_URL + '/health');
  axios.post('/users/' + id + '/roles');
}
""",
    "svc/go.mod": "module example.com/svc\n",
    "svc/client.go": """package svc

import (
	"fmt"
	"net/http"
)

const base = "/v2"

func calls(id string) {
	http.Get(fmt.Sprintf("%s/users/%s", base, id))
	http.Get("/ping")
	http.Get(base + "/items")
}
""",
    "py/pyproject.toml": '[project]\nname = "py"\n',
    "py/client.py": """import requests

BASE = "/api"


def calls(uid):
    requests.get(BASE + "/users")
    requests.get(f"/users/{uid}/x")
    requests.post("/login")
""",
}

CASES = [
    ("ts-literal", "web/src/client.ts", 5, "GET", "/plain"),
    ("ts-template-parameter", "web/src/client.ts", 6, "GET", "/items/{param}"),
    ("ts-constant-concat", "web/src/client.ts", 7, "GET", "/api/v1/users"),
    ("ts-template-constant", "web/src/client.ts", 8, "GET", "/api/v1/orders/{param}"),
    ("ts-query-ternary-in-parentheses", "web/src/client.ts", 9, "GET", "/search"),
    ("ts-query-call-in-template", "web/src/client.ts", 10, "GET", "/stats"),
    ("ts-unknown-lead-is-the-base", "web/src/client.ts", 11, "GET", "/health"),
    ("ts-concat-parameter-segment", "web/src/client.ts", 12, "POST", "/users/{param}/roles"),
    ("go-sprintf-constant", "svc/client.go", 11, "GET", "/v2/users/{param}"),
    ("go-literal", "svc/client.go", 12, "GET", "/ping"),
    ("go-constant-concat", "svc/client.go", 13, "GET", "/v2/items"),
    ("py-constant-concat", "py/client.py", 7, "GET", "/api/users"),
    ("py-f-string", "py/client.py", 8, "GET", "/users/{param}/x"),
    ("py-literal", "py/client.py", 9, "POST", "/login"),
]


@pytest.fixture(scope="module")
def calls(tmp_path_factory):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    root = tmp_path_factory.mktemp("repo")
    for rel, body in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    repo = RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root))
    with contextlib.redirect_stderr(io.StringIO()):
        res, _ = extract_and_resolve(repo)
    files = {f.id: f.path for f in res.files}
    return {(files[c.file_id], c.line): (c.method, c.path) for c in res.http_calls}


@pytest.mark.parametrize("path,line,method,expected", [c[1:] for c in CASES], ids=[c[0] for c in CASES])
def test_path_of(calls, path, line, method, expected):
    assert calls.get((path, line)) == (method, expected)
