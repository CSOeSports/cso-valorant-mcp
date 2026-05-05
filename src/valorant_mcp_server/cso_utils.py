"""CSO scouting and activity report helpers."""

from datetime import datetime, timedelta, timezone
from typing import Any


def cso_role_from_agents(agent_counts: dict[str, int]) -> dict[str, Any]:
    role_map = {
        "jett": "duelist", "raze": "duelist", "reyna": "duelist", "phoenix": "duelist",
        "neon": "duelist", "yoru": "duelist", "iso": "duelist", "waylay": "duelist",

        "omen": "controller", "brimstone": "controller", "viper": "controller",
        "astra": "controller", "harbor": "controller", "clove": "controller",

        "sova": "initiator", "breach": "initiator", "skye": "initiator",
        "kayo": "initiator", "kay/o": "initiator", "fade": "initiator",
        "gekko": "initiator", "tejo": "initiator",

        "sage": "sentinel", "cypher": "sentinel", "killjoy": "sentinel",
        "chamber": "sentinel", "deadlock": "sentinel", "vyse": "sentinel",
    }

    roles: dict[str, int] = {}

    for agent, count in agent_counts.items():
        role = role_map.get(str(agent).lower(), "unknown")
        roles[role] = roles.get(role, 0) + int(count or 0)

    primary_role = "unknown"
    if roles:
        primary_role = max(roles.items(), key=lambda item: item[1])[0]

    return {
        "primary_role": primary_role,
        "role_counts": roles,
    }


def cso_agent_counts_from_report(report: dict[str, Any]) -> dict[str, int]:
    agent_counts = report.get("agent_counts")
    if isinstance(agent_counts, dict):
        return agent_counts

    counts: dict[str, int] = {}
    for match in report.get("matches", []) or []:
        agent = match.get("agent")
        if agent and agent != "Unknown":
            counts[agent] = counts.get(agent, 0) + 1
    return counts


def parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except Exception:
        return None


def format_hhmmss(seconds: int) -> str:
    seconds = max(int(seconds), 0)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def playtime_window(days: int) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now, now - timedelta(days=days)


def extract_v4_match_meta(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("metadata") or item.get("meta") or {}


def extract_match_id(item: dict[str, Any]) -> str | None:
    meta = extract_v4_match_meta(item)
    return (
        meta.get("match_id")
        or meta.get("id")
        or item.get("match_id")
        or item.get("id")
    )


def extract_match_started_at(item: dict[str, Any]) -> datetime | None:
    meta = extract_v4_match_meta(item)
    return (
        parse_iso_datetime(meta.get("started_at"))
        or parse_iso_datetime(meta.get("game_start_patched"))
    )


def extract_match_length_seconds(item: dict[str, Any]) -> int | None:
    meta = extract_v4_match_meta(item)

    if meta.get("game_length_in_ms") is not None:
        try:
            return int(meta["game_length_in_ms"]) // 1000
        except Exception:
            pass

    if meta.get("game_length") is not None:
        try:
            value = int(meta["game_length"])
            return value // 1000 if value > 10000 else value
        except Exception:
            pass

    return None


def extract_queue_name(item: dict[str, Any]) -> str:
    meta = extract_v4_match_meta(item)
    queue = meta.get("queue")
    if isinstance(queue, dict):
        return str(queue.get("id") or queue.get("name") or "unknown").lower()
    return str(meta.get("mode_id") or meta.get("mode") or "unknown").lower()
