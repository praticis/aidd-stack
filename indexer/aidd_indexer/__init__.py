"""aidd-indexer — loads a repository's micro graph into atlas (Neo4j).

Pipeline: discovery (files, modules, stack) → extraction (tree-sitter
symbols, calls, imports) → resolution (name-based, within the repo) →
graph write (idempotent MERGE by id, orphan GC per snapshot).
"""

INDEXER_VERSION = "0.1.0"
