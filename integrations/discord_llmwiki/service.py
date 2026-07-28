"""Application services behind Discord slash commands."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Protocol, Sequence

from .projector import DiscordProjector, MessageState
from .store import EventStore


class SummaryProvider(Protocol):
    def summarize(
        self,
        previous_summary: str,
        new_messages: Sequence[str],
        retrieved_context: Sequence[str],
        *,
        safety_identifier: str | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class SearchHit:
    citation: str
    author: str
    timestamp: str
    content: str


class DiscordMemoryService:
    """Search, summary refresh, and export operations."""

    def __init__(self, store: EventStore, output_root: str | Path):
        self.store = store
        self.output_root = Path(output_root)
        self.projector = DiscordProjector(store, output_root)

    def search(self, query: str, *, limit: int = 8) -> list[SearchHit]:
        terms = [term.casefold() for term in re.findall(r"\w+", query, flags=re.UNICODE)]
        if not terms:
            return []
        projection = self.projector.replay()
        scored = []
        for message in projection.messages:
            haystack = f"{message.author_name} {message.content}".casefold()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((score, message.timestamp, message))
        scored.sort(key=lambda item: (item[0], item[1], item[2].message_id), reverse=True)
        return [self._to_hit(message) for _, _, message in scored[:limit]]

    def context_markdown(self, query: str, *, limit: int = 8) -> str:
        hits = self.search(query, limit=limit)
        if not hits:
            return "No indexed Discord evidence matched the query."
        lines = []
        for hit in hits:
            lines.extend(
                [
                    f"### {hit.author} — {hit.timestamp}",
                    f"`{hit.citation}`",
                    "",
                    hit.content or "*(no text content)*",
                    "",
                ]
            )
        return "\n".join(lines).rstrip()

    def refresh_summary(
        self,
        provider: SummaryProvider,
        *,
        max_new_messages: int = 50,
    ) -> str:
        projection = self.projector.render()
        checkpoint = int(self.store.get_metadata("summary_sequence", "0") or "0")
        recent_events = list(self.store.iter_events(after_sequence=checkpoint))
        memory_path = self.output_root / "DISCORD_MEMORY.md"
        previous = memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""
        if not recent_events:
            return previous

        current_by_id = {message.message_id: message for message in projection.messages}
        rendered = []
        seen_messages = set()
        for _, event in recent_events:
            if event.message_id in seen_messages:
                continue
            if event.event_type in {"MESSAGE_CREATE", "MESSAGE_UPDATE"}:
                message = current_by_id.get(event.message_id or "")
                if message:
                    rendered.append(self._message_for_model(message))
                    seen_messages.add(message.message_id)
            elif event.event_type == "MESSAGE_DELETE":
                rendered.append(
                    f"[discord:{event.channel_id}:{event.message_id}] message deleted"
                )
                seen_messages.add(event.message_id)
            elif event.event_type.startswith("THREAD_"):
                rendered.append(
                    f"[discord-thread:{event.channel_id}] {event.event_type.lower()}"
                )
        rendered = rendered[-max_new_messages:]
        safety_identifier = hashlib.sha256(
            (recent_events[-1][1].guild_id or "discord-local").encode("utf-8")
        ).hexdigest()[:32]
        summary = provider.summarize(
            previous,
            rendered,
            (),
            safety_identifier=safety_identifier,
        ).strip()
        if not summary.startswith("#"):
            summary = "# Current Project State\n\n" + summary
        self._write_memory(memory_path, summary + "\n")
        self.store.set_metadata("summary_sequence", str(projection.last_sequence))
        return summary

    def section(self, heading: str) -> str:
        memory_path = self.output_root / "DISCORD_MEMORY.md"
        if not memory_path.exists():
            return "Discord memory has not been summarized yet."
        memory = memory_path.read_text(encoding="utf-8")
        pattern = re.compile(
            rf"^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s|\Z)",
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        match = pattern.search(memory)
        return match.group("body").strip() if match else f"No '{heading}' section found."

    def export_markdown(self) -> Path:
        self.projector.render()
        return self.output_root / "discord" / "README.md"

    def _write_memory(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        summaries = self.output_root / "summaries"
        section_files = {
            "Decisions Made": "decisions.md",
            "Active Tasks": "tasks.md",
            "Unresolved Questions": "unresolved-questions.md",
            "Recent Activity": "rolling-summary.md",
        }
        for heading, filename in section_files.items():
            body = self.section_from_text(content, heading)
            target = summaries / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# {heading}\n\n{body}\n", encoding="utf-8", newline="\n")

    @staticmethod
    def section_from_text(markdown: str, heading: str) -> str:
        pattern = re.compile(
            rf"^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s|\Z)",
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        match = pattern.search(markdown)
        return match.group("body").strip() if match else "_No entries._"

    @staticmethod
    def _to_hit(message: MessageState) -> SearchHit:
        return SearchHit(
            citation=f"discord:{message.channel_id}:{message.message_id}",
            author=message.author_name,
            timestamp=message.timestamp,
            content=message.content,
        )

    @staticmethod
    def _message_for_model(message: MessageState) -> str:
        return "\n".join(
            [
                f"[discord:{message.channel_id}:{message.message_id}]",
                f"author: {message.author_name}",
                f"time: {message.timestamp}",
                message.content,
            ]
        )
