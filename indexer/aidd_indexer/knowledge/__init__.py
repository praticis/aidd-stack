"""Project knowledge service (docs/knowledge-contract.md): insight notes in the vault, their Qdrant
mirror, the project index's knowledge block, and the effective process policy.

    vault.py    files: names, frontmatter, owned blocks between `aidd:` markers, atomic writes
    insights.py the insight note model (read, create, update) and the knowledge block
    vectors.py  embeddings (FastEmbed, the model mcp-qdrant uses) and the Qdrant mirror
    service.py  record_insight / insights_for / policy_for — the deterministic half of the contract
    server.py   the `knowledge` MCP server
"""
