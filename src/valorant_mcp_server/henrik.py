"""Shared helpers for Henrik Dev API wrapper tools."""

import os
from typing import Any

import httpx
from dotenv import load_dotenv

_ = load_dotenv()

HENRIK_BASE_URL = "https://api.henrikdev.xyz"
HENRIK_TIMEOUT_SECONDS = float(os.getenv("HENRIK_TIMEOUT_SECONDS", "30"))


def build_error(
    message: str,
    *,
    path: str,
    params: dict[str, Any] | None = None,
    status_code: int | None = None,
    response: Any = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": True,
        "message": message,
        "path": path,
        "params": params or {},
    }
    if status_code is not None:
        payload["status_code"] = status_code
    if response is not None:
        payload["response"] = response
    return payload


def get_api_key() -> str | None:
    return os.getenv("HENRIK_API_KEY")


def build_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    api_key = get_api_key()
    if api_key:
        headers["Authorization"] = api_key
    return headers


async def henrik_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    if not get_api_key():
        return build_error(
            "HENRIK_API_KEY is not set",
            path=path,
            params=clean_params,
        )

    try:
        async with httpx.AsyncClient(timeout=HENRIK_TIMEOUT_SECONDS) as client:
            response = await client.get(
                f"{HENRIK_BASE_URL}{path}",
                headers=build_headers(),
                params=clean_params,
            )
    except httpx.HTTPError as exc:
        return build_error(
            str(exc),
            path=path,
            params=clean_params,
        )

    try:
        payload = response.json()
    except Exception:
        payload = {"raw": response.text}

    if response.status_code >= 400:
        return build_error(
            f"Henrik API returned HTTP {response.status_code}",
            path=path,
            params=clean_params,
            status_code=response.status_code,
            response=payload,
        )

    return payload


def content_slice(payload: dict[str, Any], key: str) -> dict[str, Any]:
    data = payload.get("data", payload)
    return {
        "version": data.get("version"),
        key: data.get(key, []),
    }
