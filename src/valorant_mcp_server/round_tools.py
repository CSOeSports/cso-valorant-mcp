"""Compact match-round and coaching analytics helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


TEAM_NAMES = ("Red", "Blue")


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _round_id(round_row: dict[str, Any]) -> int:
    return _safe_int(round_row.get("id") or round_row.get("round") or round_row.get("round_id"))


def _player_label(player: Any) -> str | None:
    if not isinstance(player, dict):
        return None
    name = player.get("name") or player.get("gameName") or player.get("game_name")
    tag = player.get("tag") or player.get("tagLine") or player.get("tag_line")
    if name and tag:
        return f"{name}#{tag}"
    return player.get("puuid")


def _player_key(player: Any) -> str | None:
    if not isinstance(player, dict):
        return None
    return player.get("puuid") or _player_label(player)


def _player_team(player: Any) -> str | None:
    if not isinstance(player, dict):
        return None
    return player.get("team") or player.get("team_id") or player.get("teamId")


def _player_lookup(match: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    players = _data(match).get("players") or []
    if isinstance(players, dict):
        rows: list[dict[str, Any]] = []
        for value in players.values():
            if isinstance(value, list):
                rows.extend(value)
        players = rows
    for player in players if isinstance(players, list) else []:
        if not isinstance(player, dict):
            continue
        key = player.get("puuid") or _player_label(player)
        if key:
            lookup[key] = player
    return lookup


def _meta(match: dict[str, Any]) -> dict[str, Any]:
    return _data(match).get("metadata") or {}


def _name(value: Any, *keys: str) -> Any:
    cur = value
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    if isinstance(cur, dict):
        return cur.get("name") or cur.get("displayName") or cur.get("id")
    return cur


def _teams(match: dict[str, Any]) -> list[dict[str, Any]]:
    teams = _data(match).get("teams") or []
    if isinstance(teams, dict):
        return [team for team in teams.values() if isinstance(team, dict)]
    return [team for team in teams if isinstance(team, dict)]


def final_score(match: dict[str, Any]) -> dict[str, int]:
    score = {team: 0 for team in TEAM_NAMES}
    for team in _teams(match):
        team_id = team.get("team_id") or team.get("teamId") or team.get("team")
        if team_id not in score:
            continue
        rounds = team.get("rounds") or {}
        score[team_id] = _safe_int(rounds.get("won") if isinstance(rounds, dict) else team.get("rounds_won"))
    return score


def base_match_summary(match: dict[str, Any], region: str | None = None) -> dict[str, Any]:
    meta = _meta(match)
    rounds = get_rounds(match)
    return {
        "match_id": meta.get("match_id") or _data(match).get("match_id"),
        "region": region or meta.get("region"),
        "map": _name(meta.get("map")) or meta.get("map_name") or meta.get("mapName"),
        "mode": _name(meta.get("queue")) or meta.get("mode") or meta.get("queue"),
        "started_at": meta.get("started_at") or meta.get("startedAt"),
        "final_score": final_score(match),
        "rounds_count": len(rounds),
    }


def get_rounds(match: dict[str, Any]) -> list[dict[str, Any]]:
    rounds = _data(match).get("rounds") or []
    rows = [row for row in rounds if isinstance(row, dict)]
    score_total = sum(final_score(match).values())
    if score_total and len(rows) > score_total:
        return rows[:score_total]
    return rows


def kills_by_round(match: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    kills = _data(match).get("kills") or []
    for kill in kills if isinstance(kills, list) else []:
        if isinstance(kill, dict):
            grouped[_safe_int(kill.get("round"))].append(kill)
    for rows in grouped.values():
        rows.sort(key=lambda item: _safe_int(item.get("time_in_round_in_ms")))
    return grouped


def score_after_by_round(rounds: list[dict[str, Any]]) -> dict[int, dict[str, int]]:
    score = {team: 0 for team in TEAM_NAMES}
    output: dict[int, dict[str, int]] = {}
    for round_row in sorted(rounds, key=_round_id):
        winner = round_row.get("winning_team")
        if winner in score:
            score[winner] += 1
        output[_round_id(round_row)] = dict(score)
    return output


def _plant(round_row: dict[str, Any]) -> dict[str, Any] | None:
    plant = round_row.get("plant")
    if not isinstance(plant, dict):
        return None
    return {
        "site": plant.get("site"),
        "time_ms": plant.get("round_time_in_ms") or plant.get("time_in_round_in_ms"),
        "player": _player_label(plant.get("player")),
    }


def _defuse(round_row: dict[str, Any]) -> dict[str, Any] | None:
    defuse = round_row.get("defuse")
    if not isinstance(defuse, dict):
        return None
    return {
        "time_ms": defuse.get("round_time_in_ms") or defuse.get("time_in_round_in_ms"),
        "player": _player_label(defuse.get("player")),
    }


def _econ(round_row: dict[str, Any]) -> dict[str, int | None]:
    values: dict[str, list[int]] = {team: [] for team in TEAM_NAMES}
    for stat in round_row.get("stats") or []:
        if not isinstance(stat, dict):
            continue
        team = _player_team(stat.get("player"))
        loadout = stat.get("economy", {}).get("loadout_value")
        if team in values and loadout is not None:
            values[team].append(_safe_int(loadout))
    return {
        f"{team}_avg_loadout": round(sum(team_values) / len(team_values))
        if team_values
        else None
        for team, team_values in values.items()
    }


def _compact_kill(kill: dict[str, Any]) -> dict[str, Any]:
    weapon = kill.get("weapon")
    return {
        "time_ms": kill.get("time_in_round_in_ms"),
        "killer": _player_label(kill.get("killer")),
        "victim": _player_label(kill.get("victim")),
        "weapon": _name(weapon),
        "assistants": [
            label
            for label in (_player_label(player) for player in kill.get("assistants") or [])
            if label
        ],
    }


def _kills_by_team(round_kills: list[dict[str, Any]]) -> dict[str, int]:
    counts = {team: 0 for team in TEAM_NAMES}
    for kill in round_kills:
        team = _player_team(kill.get("killer"))
        if team in counts:
            counts[team] += 1
    return counts


def round_summary(
    round_row: dict[str, Any],
    round_kills: list[dict[str, Any]],
    score_after: dict[str, int],
    *,
    include_kills: bool = False,
    include_economy: bool = False,
) -> dict[str, Any]:
    rid = _round_id(round_row)
    plant = _plant(round_row)
    defuse = _defuse(round_row)
    item: dict[str, Any] = {
        "round_number": rid + 1,
        "winning_team": round_row.get("winning_team"),
        "end_type": round_row.get("result") or round_row.get("end_type"),
        "attacking_team": None,
        "defending_team": None,
        "bomb_planted": plant is not None,
        "plant": plant,
        "bomb_defused": defuse is not None,
        "defuse": defuse,
        "round_score_after": score_after,
    }
    optional: dict[str, Any] = {}
    if include_kills:
        optional["first_blood"] = _compact_kill(round_kills[0]) if round_kills else None
        optional["kills_by_team"] = _kills_by_team(round_kills)
    if include_economy:
        optional["econ"] = _econ(round_row)
    if optional:
        item["optional"] = optional
    return item


def rounds_summary(
    match: dict[str, Any],
    region: str,
    *,
    include_kills: bool = False,
    include_economy: bool = False,
) -> dict[str, Any]:
    rounds = sorted(get_rounds(match), key=_round_id)
    grouped_kills = kills_by_round(match)
    scores = score_after_by_round(rounds)
    output = base_match_summary(match, region)
    output["rounds"] = [
        round_summary(
            round_row,
            grouped_kills.get(_round_id(round_row), []),
            scores.get(_round_id(round_row), {}),
            include_kills=include_kills,
            include_economy=include_economy,
        )
        for round_row in rounds
    ]
    return output


def select_round(
    match: dict[str, Any],
    *,
    round_number: int | None = None,
    round_id: int | None = None,
) -> dict[str, Any] | None:
    target = round_id if round_id is not None else (round_number - 1 if round_number is not None else None)
    if target is None:
        return None
    for round_row in get_rounds(match):
        if _round_id(round_row) == target:
            return round_row
    return None


def player_round_stats(round_row: dict[str, Any], round_kills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deaths = Counter(_player_key(kill.get("victim")) for kill in round_kills)
    assists = Counter()
    for kill in round_kills:
        for assistant in kill.get("assistants") or []:
            assists[_player_key(assistant)] += 1

    output: list[dict[str, Any]] = []
    for stat in round_row.get("stats") or []:
        if not isinstance(stat, dict):
            continue
        player = stat.get("player") or {}
        key = _player_key(player)
        damage = sum(_safe_int(event.get("damage")) for event in stat.get("damage_events") or [] if isinstance(event, dict))
        stats = stat.get("stats") or {}
        output.append(
            {
                "player": _player_label(player),
                "kills": _safe_int(stats.get("kills")),
                "deaths": _safe_int(deaths.get(key)),
                "assists": _safe_int(assists.get(key)),
                "damage": damage,
            }
        )
    return output


def one_round(
    match: dict[str, Any],
    region: str,
    *,
    round_number: int | None = None,
    round_id: int | None = None,
    include_killfeed: bool = False,
    include_player_stats: bool = False,
) -> dict[str, Any]:
    rounds = sorted(get_rounds(match), key=_round_id)
    round_row = select_round(match, round_number=round_number, round_id=round_id)
    if round_row is None:
        return {
            **base_match_summary(match, region),
            "error": True,
            "message": "Round not found",
            "requested_round_number": round_number,
            "requested_round_id": round_id,
        }
    grouped_kills = kills_by_round(match)
    rid = _round_id(round_row)
    output = {
        **base_match_summary(match, region),
        **round_summary(round_row, grouped_kills.get(rid, []), score_after_by_round(rounds).get(rid, {})),
    }
    if include_killfeed:
        output["killfeed"] = [_compact_kill(kill) for kill in grouped_kills.get(rid, [])]
    if include_player_stats:
        output["player_round_stats"] = player_round_stats(round_row, grouped_kills.get(rid, []))
    return output


def compact_events(match: dict[str, Any], region: str) -> dict[str, Any]:
    output = base_match_summary(match, region)
    events: list[dict[str, Any]] = []
    for round_row in sorted(get_rounds(match), key=_round_id):
        number = _round_id(round_row) + 1
        plant = _plant(round_row)
        if plant:
            events.append({"round_number": number, "type": "plant", **plant})
        defuse = _defuse(round_row)
        if defuse:
            events.append({"round_number": number, "type": "defuse", "site": None, **defuse})
        events.append(
            {
                "round_number": number,
                "type": "round_end",
                "time_ms": None,
                "player": None,
                "site": plant.get("site") if plant else None,
                "winning_team": round_row.get("winning_team"),
                "end_type": round_row.get("result") or round_row.get("end_type"),
            }
        )
    output["events"] = events
    return output


def team_economy_summary(match: dict[str, Any], region: str) -> dict[str, Any]:
    rounds = sorted(get_rounds(match), key=_round_id)
    output = base_match_summary(match, region)
    rows: list[dict[str, Any]] = []
    for round_row in rounds:
        econ = _econ(round_row)
        winner = round_row.get("winning_team")
        loser = "Blue" if winner == "Red" else "Red" if winner == "Blue" else None
        winner_loadout = econ.get(f"{winner}_avg_loadout") if winner else None
        loser_loadout = econ.get(f"{loser}_avg_loadout") if loser else None
        rows.append(
            {
                "round_number": _round_id(round_row) + 1,
                "winner": winner,
                "red_avg_loadout": econ.get("Red_avg_loadout"),
                "blue_avg_loadout": econ.get("Blue_avg_loadout"),
                "was_eco_win": bool(
                    winner_loadout is not None
                    and loser_loadout is not None
                    and winner_loadout + 1000 < loser_loadout
                ),
                "was_bonus_conversion": bool(
                    winner_loadout is not None
                    and loser_loadout is not None
                    and winner_loadout < loser_loadout
                ),
            }
        )
    output["rounds"] = rows
    output["eco_wins_count"] = sum(1 for row in rows if row["was_eco_win"])
    output["bonus_conversions_count"] = sum(1 for row in rows if row["was_bonus_conversion"])
    return output


def opening_duels(match: dict[str, Any], region: str) -> dict[str, Any]:
    output = base_match_summary(match, region)
    lookup = _player_lookup(match)
    rows: list[dict[str, Any]] = []
    conversions = Counter()
    first_kills = Counter()
    first_deaths = Counter()
    for round_row in sorted(get_rounds(match), key=_round_id):
        rid = _round_id(round_row)
        first = kills_by_round(match).get(rid, [None])[0]
        if not first:
            continue
        killer = first.get("killer") or {}
        victim = first.get("victim") or {}
        killer_key = _player_key(killer)
        victim_key = _player_key(victim)
        winner = round_row.get("winning_team")
        converted = _player_team(killer) == winner
        first_kills[_player_label(killer)] += 1
        first_deaths[_player_label(victim)] += 1
        if converted:
            conversions[_player_label(killer)] += 1
        rows.append(
            {
                "round_number": rid + 1,
                "first_kill": _compact_kill(first),
                "opener_agent": _name((lookup.get(killer_key or "") or {}).get("agent")),
                "victim_agent": _name((lookup.get(victim_key or "") or {}).get("agent")),
                "winning_team": winner,
                "converted": converted,
            }
        )
    output["rounds"] = rows
    output["summary"] = {
        "first_kills": dict(first_kills),
        "first_deaths": dict(first_deaths),
        "converted_openers": dict(conversions),
    }
    return output


def player_impact_summary(
    match: dict[str, Any],
    region: str,
    *,
    puuid: str | None = None,
    name: str | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    output = base_match_summary(match, region)
    players = _player_lookup(match)
    target_key = puuid
    if not target_key and name and tag:
        wanted = f"{name.lower()}#{tag.lower()}"
        for key, player in players.items():
            if (_player_label(player) or "").lower() == wanted:
                target_key = key
                break
    player = players.get(target_key or "")
    if not player:
        return {**output, "error": True, "message": "Player not found", "puuid": puuid, "name": name, "tag": tag}

    label = _player_label(player)
    kills = _data(match).get("kills") or []
    player_kills = [kill for kill in kills if _player_key(kill.get("killer")) == target_key]
    player_deaths = [kill for kill in kills if _player_key(kill.get("victim")) == target_key]
    fk_rounds = {_safe_int(kill.get("round")) for kill in player_kills if kill == kills_by_round(match).get(_safe_int(kill.get("round")), [None])[0]}
    fd_rounds = {_safe_int(kill.get("round")) for kill in player_deaths if kill == kills_by_round(match).get(_safe_int(kill.get("round")), [None])[0]}
    plants = [r for r in get_rounds(match) if _player_key((r.get("plant") or {}).get("player")) == target_key]
    defuses = [r for r in get_rounds(match) if _player_key((r.get("defuse") or {}).get("player")) == target_key]
    stats = player.get("stats") or {}
    damage = stats.get("damage") or {}
    rounds_with_kill_or_assist_or_survive = set()
    for round_row in get_rounds(match):
        rid = _round_id(round_row)
        died = any(_player_key(kill.get("victim")) == target_key for kill in kills_by_round(match).get(rid, []))
        involved = any(
            _player_key(kill.get("killer")) == target_key
            or any(_player_key(assistant) == target_key for assistant in kill.get("assistants") or [])
            for kill in kills_by_round(match).get(rid, [])
        )
        if involved or not died:
            rounds_with_kill_or_assist_or_survive.add(rid)
    rounds_count = len(get_rounds(match)) or 1
    output["player"] = {
        "player": label,
        "puuid": target_key,
        "agent": _name(player.get("agent")),
        "team": player.get("team_id") or player.get("team"),
        "acs": round(_safe_int(stats.get("score")) / rounds_count),
        "kills": _safe_int(stats.get("kills")),
        "deaths": _safe_int(stats.get("deaths")),
        "assists": _safe_int(stats.get("assists")),
        "first_kills": len(fk_rounds),
        "first_deaths": len(fd_rounds),
        "plants": len(plants),
        "defuses": len(defuses),
        "clutches": None,
        "trade_rate": None,
        "damage_dealt": _safe_int(damage.get("dealt")),
        "damage_received": _safe_int(damage.get("received")),
        "damage_delta": _safe_int(damage.get("dealt")) - _safe_int(damage.get("received")),
        "kast": round(len(rounds_with_kill_or_assist_or_survive) / rounds_count, 3),
    }
    return output


def rollup_history(matches: list[dict[str, Any]], *, group_by: str) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    for item in matches:
        key = item.get(group_by) or "Unknown"
        bucket = buckets.setdefault(
            key,
            {"matches": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0, "score": 0},
        )
        bucket["matches"] += 1
        bucket["wins"] += 1 if item.get("won") is True else 0
        bucket["kills"] += _safe_int(item.get("kills"))
        bucket["deaths"] += _safe_int(item.get("deaths"))
        bucket["assists"] += _safe_int(item.get("assists"))
        bucket["score"] += _safe_int(item.get("score"))
    rows = []
    for key, bucket in sorted(buckets.items(), key=lambda pair: (-pair[1]["matches"], pair[0])):
        matches_count = bucket["matches"] or 1
        deaths = bucket["deaths"] or 1
        rows.append(
            {
                group_by: key,
                "matches": bucket["matches"],
                "winrate": round(bucket["wins"] / matches_count, 3),
                "kd": round(bucket["kills"] / deaths, 2),
                "avg_score": round(bucket["score"] / matches_count),
                "kills": bucket["kills"],
                "deaths": bucket["deaths"],
                "assists": bucket["assists"],
            }
        )
    return {"groups": rows}
