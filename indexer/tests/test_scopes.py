"""Name bindings in one file (`core/http_scope.py`), on small TS and Go sources."""

from tree_sitter_language_pack import get_parser

from aidd_indexer.core.http_scope import END, Scopes, enclosing_function
from aidd_indexer.languages.base import node_text, walk

TS = b'''const base = "/api";
const top = base + "/x";
function a(p) {
  let url = "/v1";
  url += "/users";
  const inner = () => { const url = "/other"; return url; };
  return fetch(url + p);
}
function b() { return base; }
function c() {
  let q = "/x";
  q = q + "/y";
  return use(q);
}
'''

GO = b'''package p

var router = 1

func f() {
	router = 2
	x := 3
	_ = x
	_ = router
}
'''
GO_DECLARATIONS = frozenset({"short_var_declaration", "var_spec", "const_spec", "range_clause"})


def parse(lang: str, src: bytes):
    return get_parser(lang).parse(src).root_node


def ident(root, src: bytes, name: str, nth: int = -1):
    """The `nth` identifier spelled `name`, in document order (the last by default)."""
    found = [n for n in walk(root) if n.type == "identifier" and node_text(n, src) == name]
    return sorted(found, key=lambda n: n.start_byte)[nth]


def test_augmented_assignment_binds_to_itself():
    root = parse("typescript", TS)
    bound, val = Scopes(root, TS).binding(ident(root, TS, "url", -1))
    assert bound and node_text(val, TS) == 'url += "/users"'


def test_a_nested_functions_local_does_not_leak():
    root = parse("typescript", TS)
    scopes = Scopes(root, TS)
    use = ident(root, TS, "url", -1)
    assert scopes.assigned_before(enclosing_function(use), use, "url") is not None
    assert node_text(scopes.binding(use)[1], TS) != '"/other"'


def test_parameter_binds_with_no_value():
    root = parse("typescript", TS)
    assert Scopes(root, TS).binding(ident(root, TS, "p", -1)) == (True, None)


def test_name_no_function_binds_is_the_modules():
    root = parse("typescript", TS)
    scopes = Scopes(root, TS)
    assert scopes.binding(ident(root, TS, "base", -1)) == (False, None)
    bound, val = scopes.binding(ident(root, TS, "base", 1))
    assert bound and node_text(val, TS) == '"/api"'


def test_the_assignment_holding_the_use_is_not_its_binding():
    root = parse("typescript", TS)
    scopes = Scopes(root, TS)
    assert node_text(scopes.binding(ident(root, TS, "q", -1))[1], TS) == 'q + "/y"'
    right_side = ident(root, TS, "q", 2)
    assert node_text(scopes.binding(right_side)[1], TS) == '"/x"'


def test_binding_scope_is_the_function_or_the_module():
    root = parse("typescript", TS)
    scopes = Scopes(root, TS)
    use = ident(root, TS, "url", -1)
    assert scopes.binding_scope("url", use) == enclosing_function(use).id
    assert scopes.binding_scope("base", ident(root, TS, "base", -1)) == 0


def test_go_plain_assignment_does_not_declare():
    root = parse("go", GO)
    scopes = Scopes(root, GO, GO_DECLARATIONS)
    assert scopes.binding_scope("router", ident(root, GO, "router", -1)) == 0
    x = ident(root, GO, "x", -1)
    assert scopes.binding_scope("x", x) == enclosing_function(x).id


def test_assigned_before_end_asks_whether_the_scope_binds_at_all():
    root = parse("go", GO)
    scopes = Scopes(root, GO, GO_DECLARATIONS)
    f = enclosing_function(ident(root, GO, "x", -1))
    assert node_text(scopes.assigned_before(f, END, "x"), GO) == "3"
    assert scopes.assigned_before(f, END, "nothing") is None
