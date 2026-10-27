"""Prints the tree-sitter tree of a snippet, named nodes only, with field names.   tree.py FILE [GRAMMAR=csharp]"""
import sys
from tree_sitter_language_pack import get_parser

src = open(sys.argv[1], "rb").read()
tree = get_parser(sys.argv[2] if len(sys.argv) > 2 else "csharp").parse(src)


def show(n, depth=0, field=None):
    if not n.is_named:
        return
    text = src[n.start_byte:n.end_byte].decode()[:50].replace("\n", " ") if n.child_count == 0 else ""
    print("  " * depth + (f"{field}: " if field else "") + n.type + (f" {text!r}" if text else ""))
    for i, c in enumerate(n.children):
        show(c, depth + 1, n.field_name_for_child(i))


show(tree.root_node)
