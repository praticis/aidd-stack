import sys
from tree_sitter_language_pack import get_parser
def old(node):
    stack = [node]
    while stack:
        n = stack.pop(); yield n; stack.extend(reversed(n.children))
def cur(node):
    c = node.walk()
    while True:
        yield c.node
        if c.goto_first_child(): continue
        while not c.goto_next_sibling():
            if not c.goto_parent(): return
src = open(sys.argv[1], "rb").read()
root = get_parser(sys.argv[2]).parse(src).root_node
key = lambda n: (n.type, n.start_byte, n.end_byte)
a, b = [key(n) for n in old(root)], [key(n) for n in cur(root)]
print("root same:", a == b, len(a), len(b))
fn = next(n for n in old(root) if n.type in ("function_declaration", "method_declaration", "arrow_function"))
a, b = [key(n) for n in old(fn)], [key(n) for n in cur(fn)]
print("subtree same:", a == b, len(a), len(b))
x = next(cur(fn)); print("first is fn:", x == fn, x.id == fn.id, hash(x) == hash(fn), x is fn)
kids = [key(n) for n in cur(fn.children[-1])][:3]; print("last child walk starts:", kids, key(fn.children[-1]))
