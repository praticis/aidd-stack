"""Tree-sitter helpers that every part of the indexer uses and that know no language: the text of a node and a
pre-order walk."""

from __future__ import annotations

from collections.abc import Iterator

from tree_sitter import Node


def node_text(node: Node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def walk(node: Node) -> Iterator[Node]:
    """Pre-order traversal of `node` and everything under it. A cursor moves through the tree, so no list of children
    is built per node; a cursor made on a node never leaves it. The first node is `node` itself, the same object:
    callers tell it apart with `is`."""
    yield node
    cursor = node.walk()
    if not cursor.goto_first_child():
        return
    while True:
        yield cursor.node
        if cursor.goto_first_child():
            continue
        while not cursor.goto_next_sibling():
            if not cursor.goto_parent():
                return
