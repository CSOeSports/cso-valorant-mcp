"""HTTP client compatibility wrapper for the Henrik Dev Valorant API."""

from typing import Any

from valorant_mcp_server.henrik import build_error, build_headers, henrik_get

BASE_URL = "https://api.henrikdev.xyz"


def _build_headers() -> dict[str, str]:
    return build_headers()


async def get(path: str, params: dict[str, Any] | None = None) -> Any:
    """Make an authenticated GET request to the Henrik Dev API.

    Returns parsed JSON or a structured error dictionary. API key validation is
    lazy so importing the MCP server still works for discovery and health checks.
    """
    data = await henrik_get(path, params)

    if isinstance(data, dict) and data.get("status") not in (None, 200, 1):
        errors = data.get("errors", [{"message": "Unknown API error"}])
        message = (
            errors[0].get("message", "Unknown API error")
            if errors
            else "Unknown API error"
        )
        return build_error(
            f"Henrik API error (status {data.get('status')}): {message}",
            path=path,
            params=params,
            response=data,
        )

    return data
