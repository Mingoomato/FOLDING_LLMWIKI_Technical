"""Append-only SQLite event journal for Discord."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Iterator

from .models import DiscordEvent


SCHEMA = """
CREATE TABLE IF NOT EXISTS discord_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    guild_id TEXT,
    channel_id TEXT NOT NULL,
    message_id TEXT,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_discord_events_channel
    ON discord_events(channel_id, sequence);
CREATE INDEX IF NOT EXISTS idx_discord_events_message
    ON discord_events(message_id, sequence);
CREATE TABLE IF NOT EXISTS discord_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class EventStore:
    """Durable truth for imported and live Discord events."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def append(self, event: DiscordEvent) -> bool:
        """Append once; duplicate delivery is an acknowledged no-op."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO discord_events (
                    event_key, event_type, guild_id, channel_id, message_id,
                    occurred_at, received_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_key,
                    event.event_type,
                    event.guild_id,
                    event.channel_id,
                    event.message_id,
                    event.occurred_at,
                    event.received_at,
                    json.dumps(event.payload, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            return cursor.rowcount == 1

    def iter_events(self, *, after_sequence: int = 0) -> Iterator[tuple[int, DiscordEvent]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT sequence, event_key, event_type, guild_id, channel_id,
                       message_id, occurred_at, received_at, payload_json
                FROM discord_events
                WHERE sequence > ?
                ORDER BY sequence
                """,
                (after_sequence,),
            ).fetchall()
        for row in rows:
            yield row["sequence"], DiscordEvent(
                event_key=row["event_key"],
                event_type=row["event_type"],
                guild_id=row["guild_id"],
                channel_id=row["channel_id"],
                message_id=row["message_id"],
                occurred_at=row["occurred_at"],
                received_at=row["received_at"],
                payload=json.loads(row["payload_json"]),
            )

    def last_sequence(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM discord_events"
            ).fetchone()
        return int(row["sequence"])

    def get_metadata(self, key: str, default: str | None = None) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM discord_metadata WHERE key = ?",
                (key,),
            ).fetchone()
        return row["value"] if row else default

    def set_metadata(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO discord_metadata(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
