"""Python's scope index (languages/python/scopes.py) against CPython's own symbol table, rule by rule: every name each
scope binds or reads is classified as the compiler of the test image classifies it. The same comparison runs over
every Python file of the corpus (scripts/checks/python_scopes.py)."""

import sys
from pathlib import Path

import pytest
from tree_sitter_language_pack import get_parser

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "checks"))
from python_scopes import compare  # noqa: E402

from aidd_indexer.languages.python.scopes import PyScopes  # noqa: E402

RULES = {
    "a-class-body-is-not-seen-from-its-methods": "x = 1\nclass C:\n    x = 2\n    def m(self):\n        return x\n",
    "a-class-in-a-function-sees-the-functions-names":
        "def f():\n    x = 1\n    class C:\n        y = x\n        def m(self):\n            return x\n    return C\n",
    "a-closure-in-a-closure":
        "def f():\n    x = 1\n    def g():\n        def h():\n            return x\n        return h\n    return g\n",
    "global": "x = 1\ndef f():\n    global x\n    x = 2\ndef g():\n    global y\n    y = 3\n",
    "nonlocal": "def f():\n    x = 1\n    def g():\n        nonlocal x\n        x = 2\n        def h():\n"
                "            return x\n        return h\n    return g\n",
    "a-comprehensions-variable-is-its-own": "def f(y):\n    s = [x for x in y]\n    return x, s\n",
    "a-comprehensions-first-iterable-is-read-around-it": "class C:\n    xs = [1]\n    ys = [x for x in xs if xs]\n",
    "nested-comprehensions": "def f(m):\n    return [[i * j for i in row] for j, row in enumerate(m)]\n",
    "a-dict-and-a-set-comprehension":
        "def f(d):\n    return {k: {v for v in vs} for k, vs in d.items()}, {(a): (b) for a, b in d}\n",
    "a-generator-expression": "def f(y):\n    return sum(x for x in y), (z for z in y)\n",
    "an-assignment-expression-in-a-comprehension":
        "def f(y):\n    [w for w in y if (v := w)]\n    return v\n[u for u in [1] if (top := u)]\n",
    "defaults-decorators-and-annotations-are-read-around-a-definition":
        "def deco(f):\n    return f\nclass C:\n    k = 1\n    T = int\n    @deco\n"
        "    def m(self, a: T = k, *r: T, b=k, **o) -> T:\n        return a\n",
    "deferred-annotations-read-no-name":
        "from __future__ import annotations\ndef f(a: Unknown) -> Other:\n    b: Third = a\n    return b\n",
    "a-lambda": "def f(n):\n    return lambda a, b=n, *c, **d: a + b + n\n",
    "scopes-on-one-line":
        "class C:\n    def m(self, coerce=lambda x: x, *, key=lambda v: v): return coerce\n"
        "def f(rows):\n    return {k: [rows[i] for i in sorted(rows, key=lambda v: v)] for k in rows}\n",
    "targets-of-for-with-except-and-del":
        "def f(items):\n    for i, (j, *k) in items:\n        del i\n    with open(j) as (fh, z), z as w:\n"
        "        pass\n    try:\n        pass\n    except (ValueError, KeyError) as e:\n        pass\n"
        "    return k, fh, w\n",
    "imports": "import os.path\nimport sys as s\nfrom m import x as xx, yy\nfrom . import z\n",
    "match": "def f(cmd, Color):\n    match cmd:\n        case Point(x=px) | [px] as whole:\n"
             "            return px, whole\n        case {'k': kv, **others}:\n            return kv, others\n"
             "        case [first, *rest] if first:\n"
             "            return rest\n        case Color.RED:\n            pass\n        case _:\n            pass\n",
    "type-parameters": "def f[T](a: T) -> T:\n    return a\nclass K[U](list[U]):\n    def m(self, u: U) -> U:\n"
                       "        return u\ntype Alias[V] = list[V]\n",
    "a-type-parameters-bound": "def f[O: Base, *Ts, **P](x: O) -> O:\n    return x\n",
    "an-attribute-of-a-call-of-type-is-assigned": "type(resolver).patterns = patterns\n",
    "private-names": "class C:\n    __x = 1\n    def m(self):\n        return self.__x, __y\n",
    "f-strings": "def f(a, w):\n    return f'{a!r:>{w}}'\n",
    "async": "async def f(xs):\n    async with xs as x:\n        async for y in x:\n            await y\n"
             "    return [await z async for z in xs]\n",
    "augmented-and-annotated-assignments": "def f():\n    a: int\n    b: int = 1\n    b += 1\n    return b\nc: int\n",
    "keyword-arguments-and-attributes": "def f(o):\n    return g(key=o.attr, **o.extra)\n",
    "a-star-import": "from os import *\n",
    "a-method-named-like-an-implicit-cell": "class C:\n    def __class__(self):\n        return super().m()\n",
    "chained-and-unpacked-assignments":
        "def f(t):\n    a = b = t\n    c, *d = t\n    e.x = f[0] = a\n    return b, d\n",
}


@pytest.mark.parametrize("src", [pytest.param(s, id=i) for i, s in RULES.items()])
def test_every_name_is_classified_as_cpython_classifies_it(src):
    assert compare(src.encode()) == []


def index_of(src: str) -> tuple[PyScopes, list]:
    tree = get_parser("python").parse(src.encode())
    stack, names = [tree.root_node], []
    while stack:
        n = stack.pop()
        names += [n] if n.type == "identifier" else []
        stack.extend(n.children)
    return PyScopes(tree.root_node, src.encode()), sorted(names, key=lambda n: n.start_byte)


def test_a_name_read_in_a_closure_belongs_to_the_function_that_binds_it():
    index, names = index_of("def f():\n    x = 1\n    def g():\n        return x\n")
    read = names[-1]
    binding = index.binding(read)
    assert binding.kind == "free" and binding.scope.node.child_by_field_name("name").text == b"f"


def test_a_globals_sites_are_the_modules_and_those_of_the_functions_that_declare_it():
    index, names = index_of("x = A()\ndef setup():\n    global x\n    x = B()\ndef main():\n    return x.run()\n")
    read = [n for n in names if n.text == b"x"][-1]
    binding = index.binding(read)
    assert binding.kind == "global" and binding.scope is index.module
    assert [s.start_point[0] for s in index.sites(binding, "x")] == [0, 3]


def test_a_name_nothing_binds_is_a_global_of_no_scope_and_a_star_import_is_marked():
    index, names = index_of("from os import *\nprint(path)\n")
    assert index.binding(names[-1]) == ("global", None) and index.module.star_import


def test_a_deferred_annotations_names_read_nothing_but_know_their_scope():
    index, names = index_of("from __future__ import annotations\nclass C:\n    b: Model\n")
    model = names[-1]
    assert "Model" not in index.module.uses and index.scope_at(model).kind == "class"
