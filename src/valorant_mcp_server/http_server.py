"""HTTP entry point for the CSO Valorant MCP server.

This wrapper keeps the normal stdio entry point intact for local MCP clients,
while giving Portainer/Cloudflare a long-running HTTP transport to expose.
"""

import os

from valorant_mcp_server.server import mcp


def main() -> None:
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")

    mcp.settings.host = host
    mcp.settings.port = port
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
