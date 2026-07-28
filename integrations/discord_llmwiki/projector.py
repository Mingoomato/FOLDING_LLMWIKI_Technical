"""Deterministic replay and Markdown projection."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Any

from .models import DiscordEvent
from .store import EventStore


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "-", value.strip(), flags=re.UNICODE).strip("-._")
    return cleaned[:80] or "unnamed"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


@dataclass
class MessageState:
    message_id: str
    guild_id: str | None
    channel_id: str
    channel_name: str
    thread_id: str | None
    thread_name: str | None
    author_id: str
    author_name: str
    timestamp: str
    content: str
    reply_to: str | None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    edited: bool = False


@dataclass(frozen=True)
class Projection:
    messages: tuple[MessageState, ...]
    channel_names: dict[str, str]
    thread_names: dict[str, str]
    last_sequence: int


class DiscordProjector:
    """Rebuildable views over the immutable Discord event journal."""

    def __init__(self, store: EventStore, output_root: str | Path):
        self.store = store
        self.output_root = Path(output_root)

    def replay(self) -> Projection:
        messages: dict[str, MessageState] = {}
        channel_names: dict[str, str] = {}
        thread_names: dict[str, str] = {}
        last_sequence = 0

        for sequence, event in self.store.iter_events():
            last_sequence = sequence
            payload = event.payload
            metadata = payload.get("_llmwiki", {})
            if metadata.get("channel_name"):
                channel_names[event.channel_id] = str(metadata["channel_name"])
            elif event.channel_id not in channel_names:
                channel_names[event.channel_id] = event.channel_id
            channel_name = channel_names[event.channel_id]

            if event.event_type in {"THREAD_CREATE", "THREAD_UPDATE"}:
                thread_names[event.channel_id] = str(payload.get("name") or event.channel_id)
                continue
            if event.event_type == "THREAD_DELETE":
                thread_names.pop(event.channel_id, None)
                continue
            if event.event_type == "MESSAGE_DELETE":
                messages.pop(event.message_id or "", None)
                continue

            message_id = event.message_id or ""
            existing = messages.get(message_id)
            if event.event_type == "MESSAGE_CREATE" or existing is None:
                author = payload.get("author") or {}
                reference = payload.get("message_reference") or {}
                thread_id = metadata.get("thread_id")
                messages[message_id] = MessageState(
                    message_id=message_id,
                    guild_id=event.guild_id,
                    channel_id=event.channel_id,
                    channel_name=channel_name,
                    thread_id=str(thread_id) if thread_id else None,
                    thread_name=(
                        str(metadata["thread_name"])
                        if metadata.get("thread_name")
                        else None
                    ),
                    author_id=str(author.get("id") or "unknown"),
                    author_name=str(
                        author.get("global_name")
                        or author.get("username")
                        or metadata.get("author_name")
                        or "unknown"
                    ),
                    timestamp=str(payload.get("timestamp") or event.occurred_at),
                    content=str(payload.get("content") or ""),
                    reply_to=(
                        str(reference["message_id"])
                        if reference.get("message_id") is not None
                        else None
                    ),
                    attachments=list(payload.get("attachments") or []),
                    edited=event.event_type == "MESSAGE_UPDATE",
                )
                continue

            if "content" in payload:
                existing.content = str(payload.get("content") or "")
            if "attachments" in payload:
                existing.attachments = list(payload.get("attachments") or [])
            if payload.get("edited_timestamp"):
                existing.timestamp = str(payload["edited_timestamp"])
            existing.edited = True

        ordered = tuple(
            sorted(messages.values(), key=lambda message: (message.timestamp, message.message_id))
        )
        return Projection(ordered, channel_names, thread_names, last_sequence)

    def render(self) -> Projection:
        projection = self.replay()
        discord_root = self.output_root / "discord"
        self._write_raw_events(discord_root / "raw" / "events.jsonl")

        by_channel: dict[str, list[MessageState]] = {}
        by_thread: dict[str, list[MessageState]] = {}
        for message in projection.messages:
            by_channel.setdefault(message.channel_id, []).append(message)
            if message.thread_id:
                by_thread.setdefault(message.thread_id, []).append(message)

        for channel_id, messages in by_channel.items():
            name = projection.channel_names.get(channel_id, channel_id)
            path = discord_root / "channels" / f"{_slug(name)}--{channel_id}.md"
            _atomic_write(path, self._render_messages(f"Channel: {name}", messages))

        for thread_id, messages in by_thread.items():
            name = messages[0].thread_name or projection.thread_names.get(thread_id, thread_id)
            path = discord_root / "threads" / f"{_slug(name)}--{thread_id}.md"
            _atomic_write(path, self._render_messages(f"Thread: {name}", messages))

        index = [
            "# Discord Knowledge Source",
            "",
            f"- Last projected event sequence: `{projection.last_sequence}`",
            f"- Active messages: `{len(projection.messages)}`",
            "",
            "## Channels",
            "",
        ]
        for channel_id, name in sorted(
            projection.channel_names.items(), key=lambda item: (item[1], item[0])
        ):
            filename = f"{_slug(name)}--{channel_id}.md"
            index.append(f"- [{name}](channels/{filename})")
        _atomic_write(discord_root / "README.md", "\n".join(index) + "\n")
        return projection

    def _write_raw_events(self, path: Path) -> None:
        lines = [
            json.dumps(
                {"sequence": sequence, **event.to_dict()},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            for sequence, event in self.store.iter_events()
        ]
        _atomic_write(path, "\n".join(lines) + ("\n" if lines else ""))

    @staticmethod
    def _render_messages(title: str, messages: list[MessageState]) -> str:
        lines = [f"# {title}", ""]
        current_date = None
        for message in messages:
            try:
                parsed = datetime.fromisoformat(message.timestamp.replace("Z", "+00:00"))
                date_text = parsed.date().isoformat()
                time_text = parsed.strftime("%H:%M")
            except ValueError:
                date_text = "unknown-date"
                time_text = message.timestamp
            if date_text != current_date:
                lines.extend([f"## {date_text}", ""])
                current_date = date_text
            edited = " *(edited)*" if message.edited else ""
            lines.extend(
                [
                    f"### {time_text} — {message.author_name}{edited}",
                    "",
                    f"<a id=\"discord-{message.channel_id}-{message.message_id}\"></a>",
                    f"`discord:{message.channel_id}:{message.message_id}`",
                    "",
                ]
            )
            if message.reply_to:
                lines.extend([f"> Replying to message `{message.reply_to}`", ""])
            lines.extend([message.content or "*(no text content)*", ""])
            for attachment in message.attachments:
                filename = attachment.get("filename") or attachment.get("id") or "attachment"
                url = attachment.get("url") or ""
                lines.append(f"- Attachment: [{filename}]({url})" if url else f"- Attachment: {filename}")
            if message.attachments:
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"
