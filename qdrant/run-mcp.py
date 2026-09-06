import os
from mcp_server_qdrant.server import mcp

if __name__ == '__main__':
    # Reads environment variable settings with safe fallbacks
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "3000"))
    
    print(f"Iniciando o servidor MCP Qdrant via Streamable HTTP em http://{host}:{port}/mcp")
    mcp.run(transport='streamable-http', host=host, port=port)