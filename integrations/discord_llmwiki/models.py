"""Normalized Discord event model used by every adapter."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping


MESSAGE_EVENTS = {
    "MESSAGE_CREATE",
    "MESSAGE_UPDATE",
    "MESSAGE_DELETE",
}
THREAD_EVENTS = {
    "THREAD_CREATE",
    "THREAD_UPDATE",
    "THREAD_DELETE",
}
SUPPORTED_EVENTS = MESSAGE_EVENTS | THREAD_EVENTS


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_key(event_type: str, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        {"event_type": event_type, "payload": payload},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DiscordEvent:
    """One immutable Discord dispatch or historical-import record."""

    event_key: str
    event_type: str
    guild_id: str | None
    channel_id: str
    message_id: str | None
    occurred_at: str
    received_at: str
    payload: dict[str, Any]

    @classmethod
    def from_payload(
        cls,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        event_id: str | None = None,
        received_at: str | None = None,
    ) -> "DiscordEvent":
        if event_type not in SUPPORTED_EVENTS:
            raise ValueError(f"unsupported Discord event: {event_type}")

        normalized_payload = json.loads(json.dumps(payload, ensure_ascii=False))
        channel_id = str(normalized_payload.get("channel_id") or normalized_payload.get("id") or "")
        if not channel_id:
            raise ValueError("Discord event requires channel_id or id")

        message_id = None
        if event_type in MESSAGE_EVENTS:
            raw_message_id = normalized_payload.get("id")
            if raw_message_id is None:
                raise ValueError(f"{event_type} requires message id")
            message_id = str(raw_message_id)

        occurred_at = (
            normalized_payload.get("edited_timestamp")
            or normalized_payload.get("timestamp")
            or normalized_payload.get("thread_metadata", {}).get("archive_timestamp")
            or received_at
            or _utc_now()
        )
        return cls(
            event_key=event_id or _stable_key(event_type, normalized_payload),
            event_type=event_type,
            guild_id=(
                str(normalized_payload["guild_id"])
                if normalized_payload.get("guild_id") is not None
                else None
            ),
            channel_id=channel_id,
            message_id=message_id,
            occurred_at=str(occurred_at),
            received_at=received_at or _utc_now(),
            payload=normalized_payload,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_key": self.event_key,
            "event_type": self.event_type,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "occurred_at": self.occurred_at,
            "received_at": self.received_at,
            "payload": self.payload,
        }
