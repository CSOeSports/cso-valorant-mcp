"""
Valorant MCP Server — entry point.

Wraps the Henrik Dev Valorant API (https://docs.henrikdev.xyz/valorant/general)
as a set of MCP tools callable by any MCP-compatible AI client.

Environment variables:
  HENRIK_API_KEY  (optional) Your Henrik Dev API key for higher rate limits.
                  Without a key the API still works at the free / basic tier.

Usage:
  valorant-mcp-server              # run via installed script
  uv run valorant-mcp-server       # run via uv
  uv run mcp dev src/valorant_mcp_server/server.py  # MCP Inspector
"""

from mcp.types import ToolAnnotations
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from valorant_mcp_server.tools import accounts, leaderboard, matches, mmr

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP("Valorant MCP Server")

# ---------------------------------------------------------------------------
# Account tools
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        OpenWorldHint=True,
    )
)
async def get_account(
    name: str, tag: str, force_update: bool = False
) -> dict[str, Any]:
    """Retrieve Valorant account details by Riot ID (name + tag).

    Returns puuid, region, account level, card image URLs, and last update time.

    Args:
        name: In-game name (e.g. 'TenZ').
        tag: Tag line without '#' (e.g. 'SEN').
        force_update: Force a data refresh from Riot servers.
    """
    return await accounts.get_account(name, tag, force_update)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        OpenWorldHint=True,
    )
)
async def get_account_by_puuid(
    puuid: str, force_update: bool = False
) -> dict[str, Any]:
    """Retrieve Valorant account details by PUUID.

    Returns the same data as get_account, looked up by the player's unique PUUID.

    Args:
        puuid: Player unique identifier.
        force_update: Force a data refresh from Riot servers.
    """
    return await accounts.get_account_by_puuid(puuid, force_update)


# ---------------------------------------------------------------------------
# MMR / rank tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_mmr(
    region: Literal["eu", "na", "latam", "br", "ap", "kr"],
    name: str,
    tag: str,
    platform: Literal["pc", "console"] = "pc",
) -> dict[str, Any]:
    """Retrieve current MMR / rank details for a player by Riot ID.

    Returns tier name (e.g. 'Immortal 3'), ranked rating (RR), and
    leaderboard position for players in Radiant/Immortal.

    Args:
        region: Server region — eu, na, latam, br, ap, or kr.
        name: In-game name.
        tag: Tag line without '#'.
        platform: 'pc' (default) or 'console'.
    """
    return await mmr.get_mmr(region, name, tag, platform)


@mcp.tool()
async def get_mmr_by_puuid(
    region: Literal["eu", "na", "latam", "br", "ap", "kr"],
    puuid: str,
    platform: Literal["pc", "console"] = "pc",
) -> dict[str, Any]:
    """Retrieve current MMR / rank details for a player by PUUID.

    Args:
        region: Server region — eu, na, latam, br, ap, or kr.
        puuid: Player unique identifier.
        platform: 'pc' (default) or 'console'.
    """
    return await mmr.get_mmr_by_puuid(region, puuid, platform)


@mcp.tool()
async def get_mmr_history(
    region: Literal["eu", "na", "latam", "br", "ap", "kr"],
    puuid: str,
    platform: Literal["pc", "console"] = "pc",
) -> list[dict[str, Any]]:
    """Retrieve ranked rating (RR) change history for a player by PUUID.

    Each entry shows the RR gained/lost in a competitive match along
    with the tier, map, and date.

    Args:
        region: Server region — eu, na, latam, br, ap, or kr.
        puuid: Player unique identifier.
        platform: 'pc' (default) or 'console'.
    """
    return await mmr.get_mmr_history(region, puuid, platform)


# ---------------------------------------------------------------------------
# Match tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_match_history(
    region: Literal["eu", "na", "latam", "br", "ap", "kr"],
    name: str,
    tag: str,
    platform: Literal["pc", "console"] = "pc",
    mode: (
        Literal[
            "competitive",
            "custom",
            "deathmatch",
            "escalation",
            "teamdeathmatch",
            "newmap",
            "replication",
            "snowballfight",
            "spikerush",
            "swiftplay",
            "unrated",
        ]
        | None
    ) = None,
    map: (
        Literal[
            "Ascent",
            "Split",
            "Fracture",
            "Bind",
            "Breeze",
            "District",
            "Kasbah",
            "Piazza",
            "Lotus",
            "Pearl",
            "Icebox",
            "Haven",
        ]
        | None
    ) = None,
    size: int | None = None,
) -> list[dict[str, Any]]:
    """Retrieve recent match history for a player by Riot ID.

    Returns a list of match summaries including scores, kills, agents played,
    and match outcome for all players.

    Args:
        region: Server region — eu, na, latam, br, ap, or kr.
        name: In-game name.
        tag: Tag line without '#'.
        platform: 'pc' (default) or 'console'.
        mode: Optional game mode filter (e.g. 'competitive', 'unrated').
        map: Optional map name filter (e.g. 'Ascent').
        size: Number of matches to return.
    """
    return await matches.get_match_history(region, name, tag, platform, mode, map, size)


@mcp.tool()
async def get_match(
    region: Literal["eu", "na", "latam", "br", "ap", "kr"],
    match_id: str,
) -> dict[str, Any]:
    """Retrieve full details for a single Valorant match by match ID.

    Returns complete data: metadata, all players (agents, stats, loadouts),
    round-by-round results, kill feed, and economy.

    Args:
        region: Server region — eu, na, latam, br, ap, or kr.
        match_id: Match UUID (e.g. '696848f3-f16f-45bf-af13-e2192f81a600').
    """
    return await matches.get_match(region, match_id)


# ---------------------------------------------------------------------------
# Leaderboard tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_leaderboard(
    region: Literal["eu", "na", "latam", "br", "ap", "kr"],
    platform: Literal["pc", "console"] = "pc",
    name: str | None = None,
    tag: str | None = None,
    puuid: str | None = None,
    season_short: str | None = None,
    size: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """Retrieve the competitive leaderboard for a region and platform.

    Filter by a specific player using name+tag OR puuid (not both).
    Optionally filter by season (e.g. 'e9a1') for historical data.

    Args:
        region: Server region — eu, na, latam, br, ap, or kr.
        platform: 'pc' (default) or 'console'.
        name: Filter to a specific player name (requires tag).
        tag: Filter to a specific player tag (requires name).
        puuid: Filter by PUUID — mutually exclusive with name/tag.
        season_short: Season short code (e.g. 'e9a1') for historical leaderboards.
        size: Number of entries to return.
        page: Pagination offset (0-indexed).
    """
    return await leaderboard.get_leaderboard(
        region, platform, name, tag, puuid, season_short, size, page
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the Valorant MCP Server using stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
