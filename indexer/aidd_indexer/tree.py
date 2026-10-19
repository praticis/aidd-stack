"""Tree-sitter helpers that every part of the indexer uses and that know no language: the text of a node and a
pre-order walk."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Generic, TypeVar

from tree_sitter import Node

T = TypeVar("T")


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


class NodeCache(Generic[T]):
    """A value computed once per node of a parsed source, such as an index of a function's declarations. The key is
    the source object and the node's span and type, not `node.id`, which a later tree may reuse; the entry holds the
    source, so its id is not reused while cached. Bounded: it starts over past `limit` entries."""

    def __init__(self, build: Callable[[Node, bytes], T], limit: int = 4096) -> None:
        self.build, self.limit = build, limit
        self._data: dict[tuple, tuple[bytes, T]] = {}

    def get(self, node: Node, src: bytes) -> T:
        key = (id(src), node.start_byte, node.end_byte, node.type)
        hit = self._data.get(key)
        if hit is not None and hit[0] is src:
            return hit[1]
        if len(self._data) >= self.limit:
            self._data.clear()
        value = self.build(node, src)
        self._data[key] = (src, value)
        return value
