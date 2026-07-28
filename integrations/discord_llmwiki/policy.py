"""Collection and command-access policy helpers."""
from __future__ import annotations

from typing import Any


def parse_channel_allowlist(value: str) -> set[str] | None:
    """Parse comma-separated channel IDs; '*' is the explicit all-channels opt-in."""
    normalized = value.strip()
    if not normalized:
        raise ValueError("DISCORD_CHANNEL_ALLOWLIST is required; use '*' to opt into all channels")
    if normalized == "*":
        return None
    channel_ids = {item.strip() for item in normalized.split(",") if item.strip()}
    if not channel_ids or any(not channel_id.isdigit() for channel_id in channel_ids):
        raise ValueError("DISCORD_CHANNEL_ALLOWLIST must contain Discord channel IDs or '*'")
    return channel_ids


def channel_allowed(channel: Any, allowlist: set[str] | None) -> bool:
    if allowlist is None:
        return True
    channel_id = str(getattr(channel, "id", ""))
    parent_id = str(getattr(channel, "parent_id", "") or "")
    return channel_id in allowlist or parent_id in allowlist
