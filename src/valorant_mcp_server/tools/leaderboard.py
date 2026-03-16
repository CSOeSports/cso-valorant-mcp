"""
MCP tools for Valorant ranked leaderboard data via the Henrik Dev API.

Endpoint used:
  GET /valorant/v3/leaderboard/{region}/{platform}
"""

from typing import Any, Literal

from valorant_mcp_server import client

Region = Literal["eu", "na", "latam", "br", "ap", "kr"]
Platform = Literal["pc", "console"]
SeasonShort = Literal[
    "e1a1", "e1a2", "e1a3",
    "e2a1", "e2a2", "e2a3",
    "e3a1", "e3a2", "e3a3",
    "e4a1", "e4a2", "e4a3",
    "e5a1", "e5a2", "e5a3",
    "e6a1", "e6a2", "e6a3",
    "e7a1", "e7a2", "e7a3",
    "e8a1", "e8a2", "e8a3",
    "e9a1", "e9a2", "e9a3",
]


async def get_leaderboard(
    region: Region,
    platform: Platform = "pc",
    name: str | None = None,
    tag: str | None = None,
    puuid: str | None = None,
    season_short: SeasonShort | None = None,
    size: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """Retrieve the competitive leaderboard for a given region and platform.

    You can filter by player (name+tag OR puuid — not both) and optionally
    restrict to a specific season.

    Args:
        region: Server region. One of: eu, na, latam, br, ap, kr.
        platform: Platform to query — 'pc' (default) or 'console'.
        name: Filter leaderboard to show a specific player name.
        tag: Filter leaderboard to show a specific player tag (requires name).
        puuid: Filter by PUUID instead of name/tag (mutually exclusive with name/tag).
        season_short: Season identifier (e.g. 'e9a1') to retrieve historical data.
        size: Number of leaderboard entries to return.
        page: Pagination offset (0-indexed).

    Returns:
        A dictionary containing the leaderboard entries. Each entry includes
        puuid, gameName, tagLine, leaderboardRank, rankedRating, numberOfWins,
        and competitiveTier.
    """
    params: dict[str, Any] = {}
    if name:
        params["name"] = name
    if tag:
        params["tag"] = tag
    if puuid:
        params["puuid"] = puuid
    if season_short:
        params["season_short"] = season_short
    if size is not None:
        params["size"] = size
    if page is not None:
        params["page"] = page

    data = await client.get(
        f"/valorant/v3/leaderboard/{region}/{platform}", params=params
    )
    return data.get("data", data)
