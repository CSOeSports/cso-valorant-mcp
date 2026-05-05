"""Helpers for normalizing Henrik match payload shapes."""

from typing import Any


def safe_get(obj: Any, *keys: str, default: Any = None) -> Any:
    cur = obj
    for key in keys:
        if isinstance(cur, dict):
            cur = cur.get(key, default)
        else:
            return default
    return cur


def player_rows_from_match(match_data: dict[str, Any]) -> list[dict[str, Any]]:
    players = (
        safe_get(match_data, "data", "players", "all_players", default=None)
        or safe_get(match_data, "players", "all_players", default=None)
        or safe_get(match_data, "data", "players", default=None)
        or safe_get(match_data, "players", default=None)
        or []
    )

    if isinstance(players, dict):
        combined: list[dict[str, Any]] = []
        for value in players.values():
            if isinstance(value, list):
                combined.extend(value)
        return combined

    return players if isinstance(players, list) else []


def match_meta(match_data: dict[str, Any]) -> dict[str, Any]:
    return (
        safe_get(match_data, "data", "metadata", default=None)
        or safe_get(match_data, "metadata", default=None)
        or {}
    )


def player_identity(row: dict[str, Any]) -> str:
    name = row.get("name") or row.get("gameName") or row.get("game_name") or row.get("riotIdGameName")
    tag = row.get("tag") or row.get("tagLine") or row.get("tag_line") or row.get("riotIdTagline")
    if name and tag:
        return f"{name}#{tag}"
    return str(row.get("puuid") or row.get("id") or "unknown")


def player_stats(row: dict[str, Any]) -> dict[str, Any]:
    stats = row.get("stats") or {}
    return {
        "kills": int(stats.get("kills") or row.get("kills") or 0),
        "deaths": int(stats.get("deaths") or row.get("deaths") or 0),
        "assists": int(stats.get("assists") or row.get("assists") or 0),
        "score": int(stats.get("score") or row.get("score") or 0),
    }


def find_player_in_match(
    match_data: dict[str, Any],
    name: str | None = None,
    tag: str | None = None,
    puuid: str | None = None,
) -> dict[str, Any] | None:
    for row in player_rows_from_match(match_data):
        if puuid and row.get("puuid") == puuid:
            return row
        if name and tag:
            r_name = str(row.get("name") or row.get("gameName") or "").lower()
            r_tag = str(row.get("tag") or row.get("tagLine") or "").lower()
            if r_name == name.lower() and r_tag == tag.lower():
                return row
    return None


def agent_name(row: dict[str, Any]) -> str:
    character = row.get("character") or row.get("agent") or {}
    if isinstance(character, dict):
        return str(character.get("name") or character.get("displayName") or "Unknown")
    return str(character or "Unknown")


def map_name_from_match(match_data: dict[str, Any]) -> str:
    meta = match_meta(match_data)
    return str(meta.get("map") or meta.get("map_name") or meta.get("mapName") or "Unknown")


def team_won(row: dict[str, Any], match_data: dict[str, Any]) -> bool | None:
    player_team = row.get("team") or row.get("team_id") or row.get("teamId")
    teams = safe_get(match_data, "data", "teams", default=None) or match_data.get("teams")

    if isinstance(teams, dict) and player_team:
        team_data = teams.get(str(player_team).lower()) or teams.get(str(player_team).upper()) or teams.get(player_team)
        if isinstance(team_data, dict):
            has_won = team_data.get("has_won")
            if has_won is not None:
                return bool(has_won)

    return None
