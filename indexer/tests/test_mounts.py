"""The mount graph (`core/http_mounts.py`) on its own: routes are plain paths, `rebase` puts a prefix before one, and a
sub-router's root is `MountedRoot("/")`."""

from aidd_indexer.core.http_mounts import APP, TOP, MountedRoot, MountGraph, compose

APP_KEY, R, R2 = (0, "app"), (0, "r"), (0, "r2")


def rebase(ep: str, prefix: str) -> str:
    return (prefix.rstrip("/") + ("" if ep == "/" else ep)) or "/"


def is_root(ep: str) -> bool:
    return isinstance(ep, MountedRoot)


def settle(g: MountGraph, eps: list, **kw):
    waiting, edges = g.settle(eps, rebase, is_root, **kw)
    return eps, waiting, edges


def test_route_under_one_mount():
    g = MountGraph()
    g.mount(R, APP_KEY, "/api")
    g.register(0, R)
    assert settle(g, ["/users"]) == (["/api/users"], [], [])


def test_chain_of_mounts_joins_prefixes():
    g = MountGraph()
    g.mount(R2, R, "/v1")
    g.mount(R, APP_KEY, "/api")
    g.register(0, R2)
    assert settle(g, ["/x"])[0] == ["/api/v1/x"]


def test_router_mounted_twice_gives_a_copy_per_mount():
    g = MountGraph()
    g.mount(R, APP_KEY, "/a")
    g.mount(R, APP_KEY, "/b")
    g.register(0, R)
    assert sorted(settle(g, ["/x"])[0]) == ["/a/x", "/b/x"]


def test_router_mounted_nowhere_keeps_its_routes():
    g = MountGraph()
    g.register(0, R)
    assert settle(g, ["/x"])[0] == ["/x"]


def test_sub_router_root_needs_a_prefix():
    g = MountGraph()
    g.mount(R, APP_KEY, "")
    g.register(0, R)
    assert settle(g, [MountedRoot("/")])[0] == []


def test_sub_router_root_under_a_prefix_is_a_route():
    g = MountGraph()
    g.mount(R, APP_KEY, "/admin")
    g.register(0, R)
    assert settle(g, [MountedRoot("/")])[0] == ["/admin"]


def test_sub_router_root_on_the_application_is_slash():
    g = MountGraph()
    g.mount(R, APP_KEY, "")
    g.register(0, R)
    eps, _, _ = settle(g, [MountedRoot("/")], is_app=lambda k: k == APP_KEY)
    assert eps == ["/"]


def test_route_on_a_global_router_waits_for_compose():
    g = MountGraph()
    g.register(0, R)
    eps, waiting, edges = settle(g, ["/x"], global_of=lambda k: "var:f:r" if k == R else None)
    assert eps == ["/x"] and waiting == [("/x", "var:f:r")] and edges == []


def test_global_router_publishes_where_its_mounts_lead():
    g = MountGraph()
    g.mount(R, APP_KEY, "/api")
    _, _, edges = settle(g, [], global_of=lambda k: "var:f:r" if k == R else None)
    assert edges == [("var:f:r", TOP, "/api")]


def test_foreign_mount_of_another_files_router():
    g = MountGraph()
    g.mount(R, APP_KEY, "/api")
    _, _, edges = settle(g, [], foreign=[("var:other:sub", R, "/v1")])
    assert edges == [("var:other:sub", TOP, "/api/v1")]


def plan(waiting, edges, **kw):
    return compose(waiting, edges, rebase, is_root, **kw)


def test_compose_follows_the_chain_to_the_top():
    ep = "/x"
    out = plan([(ep, "g1")], {"g1": [("g2", "/v1")], "g2": [(TOP, "/api")]})
    assert out == {id(ep): ["/api/v1/x"]}


def test_compose_copies_per_parent():
    ep = "/x"
    out = plan([(ep, "g")], {"g": [(TOP, "/a"), (TOP, "/b")]})
    assert out == {id(ep): ["/a/x", "/b/x"]}


def test_compose_router_mounted_nowhere_keeps_the_route():
    assert plan([("/x", "g")], {}) == {}


def test_compose_root_of_a_router_mounted_nowhere_is_dropped_unless_it_is_an_app():
    root = MountedRoot("/")
    assert plan([(root, "g")], {}) == {id(root): []}
    assert plan([(root, "g")], {}, apps={"g"}) == {}


def test_compose_root_needs_a_prefix_or_the_application():
    root = MountedRoot("/")
    assert plan([(root, "g")], {"g": [(TOP, "")]}) == {id(root): []}
    assert plan([(root, "g")], {"g": [(APP, "")]}) == {id(root): ["/"]}


def test_compose_own_prefix_goes_after_the_chain():
    ep = "/x"
    assert plan([(ep, "g")], {"g": [(TOP, "/api")]}, owns={"g": ["/v3"]}) == {id(ep): ["/api/v3/x"]}
    assert plan([(ep, "g")], {}, owns={"g": ["/v3"]}) == {id(ep): ["/v3/x"]}


def test_compose_cycle_without_an_exit_gives_no_copy():
    ep = "/x"
    assert plan([(ep, "g1")], {"g1": [("g2", "/a")], "g2": [("g1", "/b")]}) == {id(ep): []}
