"""A Python call through the app's own client wrapper, asked of the type index the resolver asks: the wrapper's class is
the class the index gives the receiver, named as the index names it, and the wrapper a class inherits is the one its
MRO gives first. Each case is checked on both sides, the resolver's edge and the scanner's outbound call."""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys

import pytest

CLIENTS = """import httpx


class PartnerClient:
    def __init__(self):
        self.http = httpx.Client(base_url="http://partner")

    def _request(self, method, path):
        return self.http.request(method, path)
"""
PARTNER = "app/clients:PartnerClient._request"

HOMONYMS = {
    "app/a.py": "import httpx\n\n\nclass Client:\n    def _request(self, path):\n"
                "        return httpx.get(\"http://a\" + path)\n",
    "app/b.py": "import httpx\n\n\nclass Client:\n    def _request(self, method, path):\n"
                "        return httpx.request(method, \"http://b\" + path)\n",
}

DIAMOND = """import httpx


class LeftBase:
    def _send(self, path):
        return httpx.get("http://x" + path)


class Left(LeftBase):
    pass


class Right:
    def _send(self, path):
        return httpx.post("http://x" + path)
"""


def case(id, use, edges, calls, files=None):
    return pytest.param({"app/clients.py": CLIENTS, **(files or {}), "app/use.py": use}, edges, calls, id=id)


CASES = [
    case("an-annotated-parameter",
         "from app.clients import PartnerClient\n\n\ndef refund(client: PartnerClient, order_id):\n"
         "    return client._request(\"POST\", f\"/v1/orders/{order_id}/refund\")\n",
         {(PARTNER, "receiver-type")}, {("POST", "/v1/orders/{param}/refund")}),
    case("an-attribute-a-base-assigns",
         "from app.clients import PartnerClient\n\n\nclass Base:\n    def __init__(self):\n"
         "        self.partner = PartnerClient()\n\n\nclass Notifier(Base):\n    def notify(self, order_id):\n"
         "        return self.partner._request(\"POST\", f\"/v1/orders/{order_id}/notify\")\n",
         {(PARTNER, "receiver-type")}, {("POST", "/v1/orders/{param}/notify")}),
    case("a-module-variable-another-module-imports",
         "from app.shared import partner\n\n\ndef sync():\n    return partner._request(\"GET\", \"/v1/orders\")\n",
         {(PARTNER, "receiver-type")}, {("GET", "/v1/orders")},
         {"app/shared.py": "from app.clients import PartnerClient\n\npartner = PartnerClient()\n"}),
    case("a-class-of-a-name-another-module-has-too",
         "from app.a import Client\n\nclient = Client()\n\n\ndef go():\n    return client._request(\"/v1/a\")\n",
         {("app/a:Client._request", "receiver-type")}, {("GET", "/v1/a")}, HOMONYMS),
    case("the-mro-orders-the-bases",
         "from app.diamond import Left, Right\n\n\nclass Client(Left, Right):\n    def ping(self):\n"
         "        return self._send(\"/v1/ping\")\n",
         {("app/diamond:LeftBase._send", "receiver-type")}, {("GET", "/v1/ping")}, {"app/diamond.py": DIAMOND}),
]


def indexed(root, files: dict):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, source in {"app/__init__.py": "", **files}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(source)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)))


@pytest.mark.parametrize("files,edges,calls", CASES)
def test_the_resolver_reaches_the_wrapper_the_type_index_gives(tmp_path, files, edges, calls):
    res, rv = indexed(tmp_path, files)
    sym = {s.id: s for s in res.symbols}
    use = next(f.id for f in res.files if f.path == "app/use.py")
    assert {(sym[e.callee_id].qualified_name, e.strategy) for e in rv.calls
            if sym.get(e.caller_id) is not None and sym[e.caller_id].file_id == use
            and sym[e.callee_id].name in ("_request", "_send")} == edges


@pytest.mark.parametrize("files,edges,calls", CASES)
def test_the_scanner_goes_through_the_same_wrapper(tmp_path, files, edges, calls):
    res, _ = indexed(tmp_path, files)
    assert {(c.method, c.path) for c in res.http_calls if c.file_id.endswith("/app/use.py")} == calls


def test_cpython_runs_the_wrapper_the_mro_gives_first(tmp_path):
    for rel, source in {"app/__init__.py": "", "app/diamond.py": DIAMOND}.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(source)
    script = ("import sys, types\nsys.modules['httpx'] = types.ModuleType('httpx')\n"
              "from app.diamond import Left, Right\nclass Client(Left, Right): pass\nprint(Client._send.__qualname__)\n")
    ran = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert ran.stdout.strip() == "LeftBase._send"
