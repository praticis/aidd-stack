FROM python:3.12-slim

EXPOSE 3000
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Official MCP from Neo4j Labs (Cypher read/write + get_neo4j_schema).
RUN pip install mcp-neo4j-cypher

# HTTP transport for Claude Code / Cline / Cursor to point at http://localhost:3004/mcp/
CMD ["mcp-neo4j-cypher", "--transport", "http", "--server-host", "0.0.0.0", "--server-port", "3000", "--server-path", "/mcp/"]
