"""
Valorant MCP Server — entry point.

Wraps the Henrik Dev Valorant API (https://docs.henrikdev.xyz/valorant/general)
as a set of MCP tools callable by any MCP-compatible AI client.

Environment variables:
  HENRIK_API_KEY  (required) Your Henrik Dev API key.

Usage:
  valorant-mcp-server              # run via installed script
  uv run valorant-mcp-server       # run via uv
  uv run mcp dev src/valorant_mcp_server/server.py  # MCP Inspector
"""

import json
import os
from typing import Any
from mcp.types import ToolAnnotations

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from valorant_mcp_server.literals import (
    GameMode,
    MapName,
    Platform,
    Region,
    SeasonShort,
    EsportsRegion,
    League,
)
from valorant_mcp_server.cso_utils import (
    cso_agent_counts_from_report as _cso_agent_counts_from_report,
    cso_role_from_agents as _cso_role_from_agents,
    extract_match_id as _extract_match_id,
    extract_match_length_seconds as _extract_match_length_seconds,
    extract_match_started_at as _extract_match_started_at,
    extract_queue_name as _extract_queue_name,
    format_hhmmss as _format_hhmmss,
    playtime_window as _playtime_window,
)
from valorant_mcp_server.henrik import (
    content_slice as _content_slice,
    henrik_get as _henrik_get,
)
from valorant_mcp_server.match_utils import (
    agent_name as _agent_name,
    find_player_in_match as _find_player_in_match,
    map_name_from_match as _map_name_from_match,
    match_meta as _match_meta,
    player_identity as _player_identity,
    player_rows_from_match as _player_rows_from_match,
    player_stats as _player_stats,
    safe_get as _safe_get,
    team_won as _team_won,
)
from valorant_mcp_server.tools import accounts, leaderboard, matches, mmr, esports

def _csv_env(name: str, defaults: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return defaults

    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or defaults


DEFAULT_ALLOWED_HOSTS = [
    "localhost",
    "localhost:*",
    "127.0.0.1",
    "127.0.0.1:*",
    "valorant.csoesports.com",
    "valorant.csoesports.com:*",
]

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:*",
    "http://127.0.0.1",
    "http://127.0.0.1:*",
    "https://valorant.csoesports.com",
    "https://valorant.csoesports.com:*",
]


# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Valorant MCP Server",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_csv_env("MCP_ALLOWED_HOSTS", DEFAULT_ALLOWED_HOSTS),
        allowed_origins=_csv_env("MCP_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS),
    ),
)

# ---------------------------------------------------------------------------
# Account tools
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
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
        openWorldHint=True,
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


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def get_mmr(
    region: Region,
    name: str,
    tag: str,
    platform: Platform = "pc",
) -> dict[str, Any]:
    """Retrieve current MMR / rank details for a player by Player#Tag.

    Returns account, peak, currentposition
    and seasonal mmr info.

    Args:
        region: Server region — eu, na, latam, br, ap, or kr.
        name: In-game name.
        tag: Tag line without '#'.
        platform: 'pc' (default) or 'console'.
    """
    return await mmr.get_mmr(region, name, tag, platform)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def get_mmr_by_puuid(
    region: Region,
    puuid: str,
    platform: Platform = "pc",
) -> dict[str, Any]:
    """Retrieve current MMR / rank details for a player by PUUID.

    Args:
        region: Server region — eu, na, latam, br, ap, or kr.
        puuid: Player unique identifier.
        platform: 'pc' (default) or 'console'.
    """
    return await mmr.get_mmr_by_puuid(region, puuid, platform)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def get_mmr_history(
    region: Region,
    puuid: str,
    platform: Platform = "pc",
) -> dict[str, Any]:
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


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def get_match_history(
    region: Region,
    name: str,
    tag: str,
    platform: Platform = "pc",
    mode: GameMode | None = None,
    map_name: MapName | None = None,
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
        size: Number of matches to return. Default and max vary by API tier.
    """
    return await matches.get_match_history(
        region, name, tag, platform, mode, map_name, size
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def get_match(
    region: Region,
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


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
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
# Esports Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def get_esports_games_data(
    region: EsportsRegion | None = None,
    league: list[League] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve the current and upcoming schedule for Valorant esports matches.

    Can be filtered by a specific broader region or by an explicit list
    of leagues/tournaments.

    Args:
        region: Optional region to filter by (e.g., 'international', 'north america', 'emea').
        league: Optional list of specific leagues to filter by (e.g., ['vct_americas', 'vct_emea']).
    """
    return await esports.get_esports_games_data(region, league)




# ---------------------------------------------------------------------------
# Derived Analytics / Scouting Tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_player_summary(region: Region, name: str, tag: str, platform: Platform = "pc", match_count: int = 10) -> dict[str, Any]:
    """Summarise a player's account, current MMR, recent match volume, K/D/A, agents and maps."""
    account = await accounts.get_account(name, tag, False)
    mmr_data = await mmr.get_mmr(region, name, tag, platform)
    history = await matches.get_match_history(region, name, tag, platform, None, None, match_count)

    totals = {"kills": 0, "deaths": 0, "assists": 0}
    agents: dict[str, int] = {}
    maps_played: dict[str, int] = {}

    for item in history[:match_count]:
        match_id = item.get("match_id") or item.get("id") or item.get("metadata", {}).get("matchid")
        if not match_id:
            continue
        full = await matches.get_match(region, match_id)
        row = _find_player_in_match(full, name=name, tag=tag)
        if not row:
            continue
        st = _player_stats(row)
        for k in totals:
            totals[k] += st[k]
        agents[_agent_name(row)] = agents.get(_agent_name(row), 0) + 1
        maps_played[_map_name_from_match(full)] = maps_played.get(_map_name_from_match(full), 0) + 1

    deaths = max(totals["deaths"], 1)
    return {
        "account": account,
        "mmr": mmr_data,
        "matches_checked": min(len(history), match_count),
        "totals": totals,
        "kd": round(totals["kills"] / deaths, 2),
        "kda": round((totals["kills"] + totals["assists"]) / deaths, 2),
        "agents": agents,
        "maps": maps_played,
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_weekly_performance(region: Region, name: str, tag: str, platform: Platform = "pc", match_count: int = 20) -> dict[str, Any]:
    """Estimate recent weekly performance from the latest matches available through match history."""
    return await get_player_summary(region, name, tag, platform, match_count)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_agent_stats(region: Region, name: str, tag: str, platform: Platform = "pc", match_count: int = 20) -> dict[str, Any]:
    """Aggregate recent K/D/A by agent."""
    history = await matches.get_match_history(region, name, tag, platform, None, None, match_count)
    result: dict[str, dict[str, Any]] = {}

    for item in history[:match_count]:
        match_id = item.get("match_id") or item.get("id") or item.get("metadata", {}).get("matchid")
        if not match_id:
            continue
        full = await matches.get_match(region, match_id)
        row = _find_player_in_match(full, name=name, tag=tag)
        if not row:
            continue
        agent = _agent_name(row)
        st = _player_stats(row)
        bucket = result.setdefault(agent, {"matches": 0, "kills": 0, "deaths": 0, "assists": 0})
        bucket["matches"] += 1
        bucket["kills"] += st["kills"]
        bucket["deaths"] += st["deaths"]
        bucket["assists"] += st["assists"]

    for bucket in result.values():
        deaths = max(bucket["deaths"], 1)
        bucket["kd"] = round(bucket["kills"] / deaths, 2)
        bucket["kda"] = round((bucket["kills"] + bucket["assists"]) / deaths, 2)

    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_winrate_by_map(region: Region, name: str, tag: str, platform: Platform = "pc", match_count: int = 20) -> dict[str, Any]:
    """Aggregate recent map winrate where match team result is available."""
    history = await matches.get_match_history(region, name, tag, platform, None, None, match_count)
    result: dict[str, dict[str, Any]] = {}

    for item in history[:match_count]:
        match_id = item.get("match_id") or item.get("id") or item.get("metadata", {}).get("matchid")
        if not match_id:
            continue
        full = await matches.get_match(region, match_id)
        row = _find_player_in_match(full, name=name, tag=tag)
        if not row:
            continue
        map_name = _map_name_from_match(full)
        won = _team_won(row, full)
        bucket = result.setdefault(map_name, {"matches": 0, "wins": 0, "losses": 0, "unknown_results": 0})
        bucket["matches"] += 1
        if won is True:
            bucket["wins"] += 1
        elif won is False:
            bucket["losses"] += 1
        else:
            bucket["unknown_results"] += 1

    for bucket in result.values():
        decided = bucket["wins"] + bucket["losses"]
        bucket["winrate"] = round(bucket["wins"] / decided, 3) if decided else None

    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_recent_form(region: Region, name: str, tag: str, platform: Platform = "pc", match_count: int = 10) -> dict[str, Any]:
    """Return recent performance form and simple trend indicators."""
    summary = await get_player_summary(region, name, tag, platform, match_count)
    kd = summary.get("kd", 0)

    if kd >= 1.25:
        form = "hot"
    elif kd >= 1.0:
        form = "stable"
    elif kd >= 0.8:
        form = "struggling"
    else:
        form = "cold"

    return {
        "form": form,
        "summary": summary,
        "notes": [
            "Form is estimated from recent matches returned by the API.",
            "Use VOD review before making roster decisions."
        ],
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def analyze_match(region: Region, match_id: str, player_name: str | None = None, player_tag: str | None = None, puuid: str | None = None) -> dict[str, Any]:
    """Analyze a match and optionally a specific player inside that match."""
    full = await matches.get_match(region, match_id)
    meta = _match_meta(full)
    players = _player_rows_from_match(full)

    top_players = []
    for row in players:
        st = _player_stats(row)
        top_players.append({
            "player": _player_identity(row),
            "agent": _agent_name(row),
            **st,
            "kd": round(st["kills"] / max(st["deaths"], 1), 2),
        })

    top_players.sort(key=lambda x: (x["kills"], x["kd"]), reverse=True)

    target = None
    if player_name or puuid:
        row = _find_player_in_match(full, name=player_name, tag=player_tag, puuid=puuid)
        if row:
            st = _player_stats(row)
            target = {
                "player": _player_identity(row),
                "agent": _agent_name(row),
                **st,
                "kd": round(st["kills"] / max(st["deaths"], 1), 2),
            }

    return {
        "metadata": meta,
        "map": _map_name_from_match(full),
        "players_count": len(players),
        "top_players": top_players[:10],
        "target_player": target,
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def detect_common_mistakes(region: Region, name: str, tag: str, platform: Platform = "pc", match_count: int = 10) -> dict[str, Any]:
    """Infer common performance issues from recent stats. This is statistical, not VOD-level certainty."""
    summary = await get_player_summary(region, name, tag, platform, match_count)
    totals = summary["totals"]
    kd = summary["kd"]
    kda = summary["kda"]

    mistakes = []
    if kd < 0.85:
        mistakes.append("Low K/D: review first-death patterns, duel selection and trade spacing.")
    if kda < 1.3:
        mistakes.append("Low KDA: improve utility timing, trade participation and survival after contact.")
    if totals["assists"] < max(match_count * 3, 1):
        mistakes.append("Low assists: likely low utility conversion or limited teamfight support.")
    if len(summary.get("agents", {})) > 4:
        mistakes.append("Wide agent spread: role identity may be unclear across recent matches.")

    return {
        "player": f"{name}#{tag}",
        "matches_checked": summary["matches_checked"],
        "kd": kd,
        "kda": kda,
        "mistakes": mistakes or ["No obvious stat-level red flags found. Use VOD review for deeper diagnosis."],
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def suggest_training_focus(region: Region, name: str, tag: str, platform: Platform = "pc", match_count: int = 10) -> dict[str, Any]:
    """Suggest training focus areas based on recent stat profile."""
    issues = await detect_common_mistakes(region, name, tag, platform, match_count)
    focuses = []

    for mistake in issues["mistakes"]:
        if "Low K/D" in mistake:
            focuses.append("Death review: tag every first death, dry peek and isolated duel.")
        if "Low KDA" in mistake:
            focuses.append("Trade spacing drill: enter/follow timing and 2vX refrag setups.")
        if "Low assists" in mistake:
            focuses.append("Utility impact review: track flashes, scans, smokes and damage utility that directly enable kills.")
        if "agent spread" in mistake:
            focuses.append("Role lock: commit to 1 primary role and 2 agents for the next block.")

    return {
        "player": f"{name}#{tag}",
        "training_focus": focuses or ["Maintain current mechanics block; add one VOD review focused on mid-round decisions."],
        "source": "Derived from recent match stats. Confirm with coach/VOD review.",
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def find_players_by_rank_range(region: Region, min_rank_rating: int, max_rank_rating: int, platform: Platform = "pc", page: int = 0, size: int = 100) -> dict[str, Any]:
    """Search one leaderboard page for players within a leaderboard rank rating range."""
    board = await leaderboard.get_leaderboard(region, platform, None, None, None, None, size, page)
    entries = _safe_get(board, "data", "players", default=None) or board.get("players") or board.get("data") or []
    if isinstance(entries, dict):
        entries = list(entries.values())

    found = []
    for row in entries if isinstance(entries, list) else []:
        rr = row.get("ranked_rating") or row.get("rr") or row.get("rating") or row.get("leaderboardRank")
        try:
            rr_num = int(rr)
        except Exception:
            continue
        if min_rank_rating <= rr_num <= max_rank_rating:
            found.append(row)

    return {"page": page, "size": size, "matches": found}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def find_high_kd_players(region: Region, candidates: list[dict[str, str]], platform: Platform = "pc", min_kd: float = 1.2, match_count: int = 10) -> list[dict[str, Any]]:
    """Evaluate supplied candidate players and return those above a K/D threshold."""
    found = []
    for c in candidates:
        name = c.get("name")
        tag = c.get("tag")
        if not name or not tag:
            continue
        summary = await get_player_summary(region, name, tag, platform, match_count)
        if summary["kd"] >= min_kd:
            found.append({"name": name, "tag": tag, "kd": summary["kd"], "summary": summary})
    return found


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def identify_consistent_players(region: Region, candidates: list[dict[str, str]], platform: Platform = "pc", min_kd: float = 1.0, match_count: int = 10) -> list[dict[str, Any]]:
    """Evaluate supplied candidate players for stable recent form."""
    found = []
    for c in candidates:
        name = c.get("name")
        tag = c.get("tag")
        if not name or not tag:
            continue
        form = await get_recent_form(region, name, tag, platform, match_count)
        kd = form["summary"]["kd"]
        agents_used = len(form["summary"].get("agents", {}))
        if kd >= min_kd and agents_used <= 4:
            found.append({
                "name": name,
                "tag": tag,
                "kd": kd,
                "form": form["form"],
                "agents_used": agents_used,
            })
    return found


# ---------------------------------------------------------------------------
# CSO-Aligned Friendly Tool Names
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_rank(
    region: Region,
    name: str,
    tag: str,
    platform: Platform = "pc",
) -> dict[str, Any]:
    """Retrieve current Valorant rank using the shared CSO rank tool name."""
    return await get_mmr_v3(region, name, tag, platform)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_rank_history(
    region: Region,
    puuid: str,
    platform: Platform = "pc",
) -> dict[str, Any]:
    """Retrieve Valorant ranked rating history using the shared CSO rank-history tool name."""
    return await get_mmr_history_by_puuid(region, puuid, platform)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_match_details(region: Region, match_id: str) -> dict[str, Any]:
    """Retrieve Valorant match details using the shared CSO match-details tool name."""
    return await get_match_details_v4(region, match_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_live_status(region: Region) -> dict[str, Any]:
    """Retrieve Valorant platform status using the shared CSO status tool name."""
    return await get_server_status(region)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_static_content(content: str = "agents", locale: str | None = None) -> dict[str, Any]:
    """Retrieve static Valorant content using the shared CSO static-content tool name."""
    content_map = {
        "agents": "characters",
        "characters": "characters",
        "maps": "maps",
        "skins": "skins",
        "sprays": "sprays",
        "buddies": "buddies",
        "player_cards": "playerCards",
        "player_titles": "playerTitles",
        "seasons": "seasons",
        "game_modes": "gameModes",
    }
    payload = await get_valorant_content(locale)
    key = content_map.get(content)
    if not key:
        return {
            "error": True,
            "message": f"Unsupported content type: {content}",
            "supported_content": sorted(content_map),
        }
    return _content_slice(payload, key)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_player_activity_report(
    region: Region,
    name: str,
    tag: str,
    platform: Platform = "pc",
    days: int = 7,
    mode: str | None = None,
    page_size: int = 10,
    max_pages: int = 10,
) -> dict[str, Any]:
    """CSO player activity report using the shared activity-report tool name."""
    return await get_player_playtime(region, name, tag, platform, days, mode, page_size, max_pages)


# ---------------------------------------------------------------------------
# HenrikDev Full API Wrapper Tools
# ---------------------------------------------------------------------------

# Accounts

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_account_v1(name: str, tag: str, force: bool = False) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/account/{name}/{tag}", {"force": force})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_account_v2(name: str, tag: str, force: bool = False) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v2/account/{name}/{tag}", {"force": force})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_account_by_puuid_v1(puuid: str, force: bool = False) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/by-puuid/account/{puuid}", {"force": force})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_account_by_puuid_v2(puuid: str, force: bool = False) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v2/by-puuid/account/{puuid}", {"force": force})


# Content

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_valorant_content(locale: str | None = None) -> dict[str, Any]:
    return await _henrik_get("/valorant/v1/content", {"locale": locale})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_agents(locale: str | None = None) -> dict[str, Any]:
    return _content_slice(await get_valorant_content(locale), "characters")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_maps(locale: str | None = None) -> dict[str, Any]:
    return _content_slice(await get_valorant_content(locale), "maps")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_skins(locale: str | None = None) -> dict[str, Any]:
    return _content_slice(await get_valorant_content(locale), "skins")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_sprays(locale: str | None = None) -> dict[str, Any]:
    return _content_slice(await get_valorant_content(locale), "sprays")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_buddies(locale: str | None = None) -> dict[str, Any]:
    return _content_slice(await get_valorant_content(locale), "charms")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_player_cards(locale: str | None = None) -> dict[str, Any]:
    return _content_slice(await get_valorant_content(locale), "playerCards")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_player_titles(locale: str | None = None) -> dict[str, Any]:
    return _content_slice(await get_valorant_content(locale), "playerTitles")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_seasons(locale: str | None = None) -> dict[str, Any]:
    return _content_slice(await get_valorant_content(locale), "acts")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_game_modes(locale: str | None = None) -> dict[str, Any]:
    return _content_slice(await get_valorant_content(locale), "gameModes")


@mcp.resource("valorant://agents", description="Valorant agent static content")
async def valorant_agents_resource() -> str:
    return json.dumps(await get_agents(), indent=2, ensure_ascii=False)


@mcp.resource("valorant://maps", description="Valorant map static content")
async def valorant_maps_resource() -> str:
    return json.dumps(await get_maps(), indent=2, ensure_ascii=False)


@mcp.resource("valorant://seasons", description="Valorant season and act static content")
async def valorant_seasons_resource() -> str:
    return json.dumps(await get_seasons(), indent=2, ensure_ascii=False)


@mcp.resource("valorant://game_modes", description="Valorant game mode static content")
async def valorant_game_modes_resource() -> str:
    return json.dumps(await get_game_modes(), indent=2, ensure_ascii=False)


# Matches

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_match_history_v4(
    region: Region,
    name: str,
    tag: str,
    platform: Platform = "pc",
    mode: str | None = None,
    map_name: str | None = None,
    size: int | None = None,
    start: int | None = None,
) -> dict[str, Any]:
    return await _henrik_get(
        f"/valorant/v4/matches/{region}/{platform}/{name}/{tag}",
        {"mode": mode, "map": map_name, "size": size, "start": start},
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_match_history_by_puuid(
    region: Region,
    puuid: str,
    platform: Platform = "pc",
    mode: str | None = None,
    map_name: str | None = None,
    size: int | None = None,
    start: int | None = None,
) -> dict[str, Any]:
    return await _henrik_get(
        f"/valorant/v4/by-puuid/matches/{region}/{platform}/{puuid}",
        {"mode": mode, "map": map_name, "size": size, "start": start},
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_match_details_v4(region: Region, match_id: str) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v4/match/{region}/{match_id}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_match_details_v2(match_id: str) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v2/match/{match_id}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_stored_matches(
    region: Region,
    name: str,
    tag: str,
    mode: str | None = None,
    map_name: str | None = None,
    page: int | None = None,
    size: int | None = None,
) -> dict[str, Any]:
    return await _henrik_get(
        f"/valorant/v1/stored-matches/{region}/{name}/{tag}",
        {"mode": mode, "map": map_name, "page": page, "size": size},
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_stored_matches_by_puuid(
    region: Region,
    puuid: str,
    mode: str | None = None,
    map_name: str | None = None,
    page: int | None = None,
    size: int | None = None,
) -> dict[str, Any]:
    return await _henrik_get(
        f"/valorant/v1/by-puuid/stored-matches/{region}/{puuid}",
        {"mode": mode, "map": map_name, "page": page, "size": size},
    )


# MMR

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_mmr_v3(region: Region, name: str, tag: str, platform: Platform = "pc") -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v3/mmr/{region}/{platform}/{name}/{tag}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_mmr_by_puuid_v3(region: Region, puuid: str, platform: Platform = "pc") -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v3/by-puuid/mmr/{region}/{platform}/{puuid}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_mmr_history_v1(region: Region, name: str, tag: str) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/mmr-history/{region}/{name}/{tag}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_mmr_history_by_puuid(region: Region, puuid: str, platform: Platform = "pc") -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v2/by-puuid/mmr-history/{region}/{platform}/{puuid}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_stored_mmr_history(region: Region, name: str, tag: str, page: int | None = None, size: int | None = None) -> dict[str, Any]:
    return await _henrik_get(
        f"/valorant/v1/stored-mmr-history/{region}/{name}/{tag}",
        {"page": page, "size": size},
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_stored_mmr_history_v2(
    region: Region,
    name: str,
    tag: str,
    platform: Platform = "pc",
    page: int | None = None,
    size: int | None = None,
) -> dict[str, Any]:
    return await _henrik_get(
        f"/valorant/v2/stored-mmr-history/{region}/{platform}/{name}/{tag}",
        {"page": page, "size": size},
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_stored_mmr_history_by_puuid(
    region: Region,
    puuid: str,
    platform: Platform = "pc",
    page: int | None = None,
    size: int | None = None,
) -> dict[str, Any]:
    return await _henrik_get(
        f"/valorant/v2/by-puuid/stored-mmr-history/{region}/{platform}/{puuid}",
        {"page": page, "size": size},
    )


# Leaderboard

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_leaderboard_v3(
    region: Region,
    platform: Platform = "pc",
    puuid: str | None = None,
    name: str | None = None,
    tag: str | None = None,
    season_short: str | None = None,
    season_id: str | None = None,
    size: int | None = None,
    start_index: int | None = None,
) -> dict[str, Any]:
    return await _henrik_get(
        f"/valorant/v3/leaderboard/{region}/{platform}",
        {
            "puuid": puuid,
            "name": name,
            "tag": tag,
            "season_short": season_short,
            "season_id": season_id,
            "size": size,
            "start_index": start_index,
        },
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_leaderboard_player_by_name(region: Region, name: str, tag: str, platform: Platform = "pc") -> dict[str, Any]:
    return await get_leaderboard_v3(region, platform, None, name, tag, None, None, 1, None)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_leaderboard_player_by_puuid(region: Region, puuid: str, platform: Platform = "pc") -> dict[str, Any]:
    return await get_leaderboard_v3(region, platform, puuid, None, None, None, None, 1, None)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_leaderboard_by_season(region: Region, season_short: str, platform: Platform = "pc", size: int | None = None, start_index: int | None = None) -> dict[str, Any]:
    return await get_leaderboard_v3(region, platform, None, None, None, season_short, None, size, start_index)


# Premier

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_premier_team_by_name(team_name: str, team_tag: str) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/premier/{team_name}/{team_tag}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_premier_team_by_id(team_id: str) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/premier/{team_id}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_premier_team_history_by_name(team_name: str, team_tag: str) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/premier/{team_name}/{team_tag}/history")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_premier_team_history_by_id(team_id: str) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/premier/{team_id}/history")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def search_premier_teams(name: str | None = None, tag: str | None = None, division: int | None = None) -> dict[str, Any]:
    return await _henrik_get("/valorant/v1/premier/search", {"name": name, "tag": tag, "division": division})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_premier_conferences() -> dict[str, Any]:
    return await _henrik_get("/valorant/v1/premier/conferences")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_premier_seasons(region: Region) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/premier/seasons/{region}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_premier_leaderboard_region(region: Region) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/premier/leaderboard/{region}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_premier_leaderboard_conference(region: Region, conference: str) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/premier/leaderboard/{region}/{conference}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_premier_leaderboard_division(region: Region, conference: str, division: int) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/premier/leaderboard/{region}/{conference}/{division}")


# Esports

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_esports_schedule(region: EsportsRegion | None = None, league: list[League] | None = None) -> list[dict[str, Any]]:
    return await esports.get_esports_games_data(region, league)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_esports_schedule_by_region(region: EsportsRegion) -> list[dict[str, Any]]:
    return await esports.get_esports_games_data(region, None)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_esports_schedule_by_league(league: list[League]) -> list[dict[str, Any]]:
    return await esports.get_esports_games_data(None, league)


# Queue / Status / Version / Store / Website

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_queue_status(region: Region) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/queue-status/{region}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_server_status(region: Region) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/status/{region}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_valorant_version(region: Region) -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/version/{region}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_store_featured_v1() -> dict[str, Any]:
    return await _henrik_get("/valorant/v1/store-featured")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_store_featured_v2() -> dict[str, Any]:
    return await _henrik_get("/valorant/v2/store-featured")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_valorant_news(countrycode: str = "en-us") -> dict[str, Any]:
    return await _henrik_get(f"/valorant/v1/website/{countrycode}")





# ---------------------------------------------------------------------------
# Phase 3 – CSO Academy / Scouting Tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_academy_weekly_playtime_report(
    players: list[dict[str, str]],
    default_region: Region = "eu",
    default_platform: Platform = "pc",
    mode: str | None = None,
    page_size: int = 10,
    max_pages: int = 10,
) -> dict[str, Any]:
    """Weekly CSO Academy playtime report for multiple players.

    Each player dict should contain name and tag.
    Optional per-player fields: region, platform.
    """
    reports: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for player in players:
        name = player.get("name")
        tag = player.get("tag")
        region = player.get("region", default_region)
        platform = player.get("platform", default_platform)

        if not name or not tag:
            errors.append({"input": player, "error": "missing name/tag"})
            continue

        try:
            report = await get_weekly_activity_report(
                region=region,
                name=name,
                tag=tag,
                platform=platform,
                mode=mode,
                page_size=page_size,
                max_pages=max_pages,
            )
            reports.append(report)
        except Exception as exc:
            errors.append({
                "input": player,
                "error": str(exc),
            })

    ranked = sorted(
        reports,
        key=lambda r: int(r.get("matches_counted") or 0),
        reverse=True,
    )

    inactive = [r for r in ranked if int(r.get("matches_counted") or 0) == 0]
    low_volume = [r for r in ranked if 0 < int(r.get("matches_counted") or 0) < 5]

    return {
        "players_checked": len(players),
        "reports": ranked,
        "inactive_players": inactive,
        "low_volume_players": low_volume,
        "errors": errors,
        "notes": [
            "Use confidence and audit tools before making roster decisions.",
            "This is activity intelligence, not a replacement for VOD or trial review.",
        ],
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_role_profile(
    region: Region,
    name: str,
    tag: str,
    platform: Platform = "pc",
    days: int = 14,
    page_size: int = 10,
    max_pages: int = 10,
) -> dict[str, Any]:
    """Estimate a player role profile from recent agent pool."""
    report = await get_player_playtime(
        region=region,
        name=name,
        tag=tag,
        platform=platform,
        days=days,
        mode=None,
        page_size=page_size,
        max_pages=max_pages,
    )

    agent_counts = _cso_agent_counts_from_report(report)
    role = _cso_role_from_agents(agent_counts)
    agent_pool_size = len(agent_counts)

    if agent_pool_size == 0:
        role_stability = "unknown"
    elif agent_pool_size <= 2:
        role_stability = "high"
    elif agent_pool_size <= 4:
        role_stability = "medium"
    else:
        role_stability = "wide_pool"

    return {
        "player": report.get("player"),
        "window": report.get("window"),
        "matches_counted": report.get("matches_counted"),
        "agent_counts": agent_counts,
        "agent_pool_size": agent_pool_size,
        "primary_role": role["primary_role"],
        "role_counts": role["role_counts"],
        "role_stability": role_stability,
        "confidence": report.get("confidence"),
        "notes": (report.get("notes") or [])
        + ([] if agent_counts else ["No agent data could be extracted from the counted matches."]),
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_consistency_score(
    region: Region,
    name: str,
    tag: str,
    platform: Platform = "pc",
    days: int = 14,
    page_size: int = 10,
    max_pages: int = 10,
) -> dict[str, Any]:
    """Score player consistency from active days, match volume, playtime and role stability."""
    activity = await get_player_playtime(
        region=region,
        name=name,
        tag=tag,
        platform=platform,
        days=days,
        mode=None,
        page_size=page_size,
        max_pages=max_pages,
    )

    role = await get_role_profile(
        region=region,
        name=name,
        tag=tag,
        platform=platform,
        days=days,
        page_size=page_size,
        max_pages=max_pages,
    )

    matches = int(activity.get("matches_counted") or 0)
    active_days = int(activity.get("active_days") or len(activity.get("daily_breakdown", {}) or {}))
    total_seconds = int(activity.get("total_playtime_seconds") or 0)
    agent_pool_size = int(role.get("agent_pool_size") or 0)

    match_score = min(matches / 20, 1.0)
    active_day_score = min((active_days / max(days, 1)) / 0.6, 1.0)
    playtime_score = min(total_seconds / (10 * 3600), 1.0)

    if agent_pool_size <= 2:
        role_score = 1.0
    elif agent_pool_size <= 4:
        role_score = 0.75
    else:
        role_score = 0.45

    score = round(
        (
            match_score * 0.30
            + active_day_score * 0.30
            + playtime_score * 0.25
            + role_score * 0.15
        ) * 100
    )

    return {
        "player": activity.get("player"),
        "score": score,
        "rating": "high" if score >= 75 else "medium" if score >= 50 else "low",
        "matches_counted": matches,
        "active_days": active_days,
        "total_playtime_hhmmss": activity.get("total_playtime_hhmmss"),
        "agent_pool_size": agent_pool_size,
        "role_stability": role.get("role_stability"),
        "confidence": activity.get("confidence"),
        "notes": activity.get("notes", []),
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_trial_readiness_score(
    region: Region,
    name: str,
    tag: str,
    platform: Platform = "pc",
    days: int = 14,
    page_size: int = 10,
    max_pages: int = 10,
) -> dict[str, Any]:
    """CSO scouting readiness score.

    Combines activity consistency, role stability, MMR and recent form.
    This is scouting support only. Human coach review is required.
    """
    consistency = await get_consistency_score(
        region=region,
        name=name,
        tag=tag,
        platform=platform,
        days=days,
        page_size=page_size,
        max_pages=max_pages,
    )

    role = await get_role_profile(
        region=region,
        name=name,
        tag=tag,
        platform=platform,
        days=days,
        page_size=page_size,
        max_pages=max_pages,
    )

    recent = await get_recent_form(region, name, tag, platform, 10)
    mmr_payload = await get_mmr_v3(region, name, tag, platform)

    kd = recent.get("summary", {}).get("kd", 0) or 0
    try:
        kd_float = float(kd)
    except Exception:
        kd_float = 0.0

    kd_score = min(kd_float / 1.25, 1.0) * 100
    activity_score = float(consistency.get("score") or 0)

    role_stability = role.get("role_stability")
    role_score = 100 if role_stability == "high" else 75 if role_stability == "medium" else 55

    final_score = round(
        activity_score * 0.45
        + kd_score * 0.35
        + role_score * 0.20
    )

    return {
        "player": f"{name}#{tag}",
        "trial_readiness_score": final_score,
        "rating": "trial_ready" if final_score >= 75 else "watchlist" if final_score >= 55 else "not_ready",
        "consistency": consistency,
        "role_profile": role,
        "recent_form": recent,
        "mmr": mmr_payload,
        "human_review_required": True,
        "notes": [
            "Score supports scouting triage only.",
            "Confirm with VOD review, comms review, trial block, and coach judgement.",
        ],
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def compare_players(
    players: list[dict[str, str]],
    default_region: Region = "eu",
    default_platform: Platform = "pc",
    days: int = 14,
    page_size: int = 10,
    max_pages: int = 10,
) -> dict[str, Any]:
    """Compare candidate players side-by-side for CSO Academy scouting."""
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for player in players:
        name = player.get("name")
        tag = player.get("tag")
        region = player.get("region", default_region)
        platform = player.get("platform", default_platform)

        if not name or not tag:
            errors.append({"input": player, "error": "missing name/tag"})
            continue

        try:
            score = await get_trial_readiness_score(
                region=region,
                name=name,
                tag=tag,
                platform=platform,
                days=days,
                page_size=page_size,
                max_pages=max_pages,
            )
            results.append(score)
        except Exception as exc:
            errors.append({
                "input": player,
                "error": str(exc),
            })

    ranked = sorted(
        results,
        key=lambda item: int(item.get("trial_readiness_score") or 0),
        reverse=True,
    )

    return {
        "players_compared": len(players),
        "ranked": ranked,
        "errors": errors,
        "human_review_required": True,
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_player_playtime(
    region: Region,
    name: str,
    tag: str,
    platform: Platform = "pc",
    days: int = 7,
    mode: str | None = None,
    page_size: int = 10,
    max_pages: int = 10,
) -> dict[str, Any]:
    """Calculate player playtime over a date window using v4 match metadata.

    Uses v4 match history metadata.started_at and metadata.game_length_in_ms.
    This is designed for weekly reporting and is more accurate than match-count estimates.

    Args:
        region: Server region.
        name: Riot name.
        tag: Riot tag without '#'.
        platform: pc or console.
        days: Lookback window in days. Default 7.
        mode: Optional queue filter, e.g. competitive, swiftplay, unrated.
        page_size: Henrik v4 matchlist page size. Docs indicate max 10.
        max_pages: Number of pages to scan.
    """
    now, window_start = _playtime_window(days)

    total_seconds = 0
    counted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    agent_lookup_errors: list[dict[str, Any]] = []
    daily: dict[str, dict[str, Any]] = {}
    modes: dict[str, dict[str, Any]] = {}
    agent_counts: dict[str, int] = {}

    seen_match_ids: set[str] = set()
    stopped_due_to_old_match = False

    page_size = max(1, min(int(page_size), 10))
    max_pages = max(1, min(int(max_pages), 25))

    for page in range(max_pages):
        start = page * page_size

        payload = await get_match_history_v4(
            region=region,
            name=name,
            tag=tag,
            platform=platform,
            mode=mode,
            map_name=None,
            size=page_size,
            start=start,
        )

        if payload.get("error"):
            skipped.append({
                "reason": "api_error",
                "page": page,
                "payload": payload,
            })
            break

        matches_list = payload.get("data") or []
        if not isinstance(matches_list, list) or not matches_list:
            break

        for item in matches_list:
            match_id = _extract_match_id(item)
            if match_id and match_id in seen_match_ids:
                continue
            if match_id:
                seen_match_ids.add(match_id)

            started_at = _extract_match_started_at(item)
            length_seconds = _extract_match_length_seconds(item)
            queue_name = _extract_queue_name(item)

            if not started_at:
                skipped.append({
                    "match_id": match_id,
                    "reason": "missing_started_at",
                })
                continue

            if started_at < window_start:
                stopped_due_to_old_match = True
                continue

            if length_seconds is None:
                skipped.append({
                    "match_id": match_id,
                    "started_at": started_at.isoformat(),
                    "reason": "missing_game_length",
                })
                continue

            date_key = started_at.date().isoformat()
            total_seconds += length_seconds

            daily_bucket = daily.setdefault(date_key, {
                "matches": 0,
                "seconds": 0,
                "hhmmss": "00:00:00",
            })
            daily_bucket["matches"] += 1
            daily_bucket["seconds"] += length_seconds
            daily_bucket["hhmmss"] = _format_hhmmss(daily_bucket["seconds"])

            mode_bucket = modes.setdefault(queue_name, {
                "matches": 0,
                "seconds": 0,
                "hhmmss": "00:00:00",
            })
            mode_bucket["matches"] += 1
            mode_bucket["seconds"] += length_seconds
            mode_bucket["hhmmss"] = _format_hhmmss(mode_bucket["seconds"])

            counted_match = {
                "match_id": match_id,
                "started_at": started_at.isoformat(),
                "queue": queue_name,
                "seconds": length_seconds,
                "hhmmss": _format_hhmmss(length_seconds),
            }

            if match_id:
                try:
                    details = await get_match_details_v4(region, match_id)
                    player_row = _find_player_in_match(details, name=name, tag=tag)
                    if player_row:
                        agent = _agent_name(player_row)
                        counted_match["agent"] = agent
                        if agent != "Unknown":
                            agent_counts[agent] = agent_counts.get(agent, 0) + 1
                except Exception as exc:
                    agent_lookup_errors.append({
                        "match_id": match_id,
                        "error": str(exc),
                    })

            counted.append(counted_match)

        if stopped_due_to_old_match:
            break

    confidence = "high"
    notes = []

    if skipped:
        confidence = "medium"
        notes.append("Some matches were skipped because metadata was missing or an API page failed.")

    if agent_lookup_errors:
        notes.append("Some match details could not be fetched for agent-role enrichment.")

    if not stopped_due_to_old_match and len(counted) >= page_size * max_pages:
        confidence = "medium"
        notes.append("Scan reached max_pages before confirming the full date window. Increase max_pages for complete coverage.")

    if not counted:
        confidence = "low"
        notes.append("No matches with usable duration metadata were found in the requested window.")

    return {
        "player": f"{name}#{tag}",
        "region": region,
        "platform": platform,
        "window": {
            "days": days,
            "from": window_start.isoformat(),
            "to": now.isoformat(),
        },
        "mode_filter": mode,
        "total_playtime_seconds": total_seconds,
        "total_playtime_hhmmss": _format_hhmmss(total_seconds),
        "matches_counted": len(counted),
        "matches_skipped": len(skipped),
        "daily_breakdown": daily,
        "mode_breakdown": modes,
        "agent_counts": agent_counts,
        "matches": counted,
        "skipped": skipped[:20],
        "agent_lookup_errors": agent_lookup_errors[:20],
        "confidence": confidence,
        "notes": notes,
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_player_playtime_audit(
    region: Region,
    name: str,
    tag: str,
    platform: Platform = "pc",
    days: int = 7,
    mode: str | None = None,
    page_size: int = 10,
    max_pages: int = 10,
) -> dict[str, Any]:
    """Return auditable match-by-match evidence for player playtime.

    Use this when coaches need to verify exactly which matches were counted,
    skipped, and why.
    """
    report = await get_player_playtime(
        region=region,
        name=name,
        tag=tag,
        platform=platform,
        days=days,
        mode=mode,
        page_size=page_size,
        max_pages=max_pages,
    )

    return {
        "player": report.get("player"),
        "region": report.get("region"),
        "platform": report.get("platform"),
        "window": report.get("window"),
        "mode_filter": report.get("mode_filter"),
        "total_playtime_hhmmss": report.get("total_playtime_hhmmss"),
        "matches_counted": report.get("matches_counted"),
        "matches_skipped": report.get("matches_skipped"),
        "agent_counts": report.get("agent_counts", {}),
        "confidence": report.get("confidence"),
        "counted_matches": report.get("matches", []),
        "skipped_matches": report.get("skipped", []),
        "agent_lookup_errors": report.get("agent_lookup_errors", []),
        "notes": report.get("notes", []),
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def get_weekly_activity_report(
    region: Region,
    name: str,
    tag: str,
    platform: Platform = "pc",
    mode: str | None = None,
    page_size: int = 10,
    max_pages: int = 10,
) -> dict[str, Any]:
    """CSO weekly activity report for one player.

    Reports hours played, match volume, active days, mode split, longest day,
    and confidence. Uses get_player_playtime internally.
    """
    report = await get_player_playtime(
        region=region,
        name=name,
        tag=tag,
        platform=platform,
        days=7,
        mode=mode,
        page_size=page_size,
        max_pages=max_pages,
    )

    daily = report.get("daily_breakdown", {}) or {}
    longest_day = None

    if daily:
        day_key, day_value = max(
            daily.items(),
            key=lambda item: item[1].get("seconds", 0),
        )
        longest_day = {
            "date": day_key,
            **day_value,
        }

    return {
        "player": report.get("player"),
        "region": report.get("region"),
        "platform": report.get("platform"),
        "window": report.get("window"),
        "total_playtime_seconds": report.get("total_playtime_seconds"),
        "total_playtime_hhmmss": report.get("total_playtime_hhmmss"),
        "matches_counted": report.get("matches_counted"),
        "matches_skipped": report.get("matches_skipped"),
        "active_days": len(daily),
        "longest_day": longest_day,
        "daily_breakdown": daily,
        "mode_breakdown": report.get("mode_breakdown", {}),
        "agent_counts": report.get("agent_counts", {}),
        "confidence": report.get("confidence"),
        "notes": report.get("notes", []),
        "audit_available": True,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the Valorant MCP Server using HTTP transport."""
    mcp.settings.host = os.getenv("MCP_HOST", "0.0.0.0")
    mcp.settings.port = int(os.getenv("MCP_PORT", "8000"))

    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
