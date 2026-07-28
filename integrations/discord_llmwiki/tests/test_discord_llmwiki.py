from __future__ import annotations

import json
from pathlib import Path

import pytest

from integrations.discord_llmwiki.models import DiscordEvent
from integrations.discord_llmwiki.openai_provider import OpenAIResponsesSummarizer
from integrations.discord_llmwiki.policy import parse_channel_allowlist
from integrations.discord_llmwiki.projector import DiscordProjector
from integrations.discord_llmwiki.rest import DiscordRestClient
from integrations.discord_llmwiki.service import DiscordMemoryService
from integrations.discord_llmwiki.store import EventStore


def message_payload(
    message_id: str,
    content: str,
    *,
    channel_id: str = "10",
    timestamp: str = "2026-07-29T01:25:00+09:00",
    reply_to: str | None = None,
) -> dict:
    payload = {
        "id": message_id,
        "guild_id": "1",
        "channel_id": channel_id,
        "timestamp": timestamp,
        "content": content,
        "author": {"id": "7", "username": "Mingoomato"},
        "attachments": [],
        "_llmwiki": {"channel_name": "backend"},
    }
    if reply_to:
        payload["message_reference"] = {"message_id": reply_to}
    return payload


def test_event_key_is_stable_for_historical_import():
    first = DiscordEvent.from_payload(
        "MESSAGE_CREATE",
        message_payload("100", "hello"),
        received_at="2026-01-01T00:00:00+00:00",
    )
    second = DiscordEvent.from_payload(
        "MESSAGE_CREATE",
        message_payload("100", "hello"),
        received_at="2026-01-02T00:00:00+00:00",
    )
    assert first.event_key == second.event_key


def test_event_rejects_unknown_dispatch():
    with pytest.raises(ValueError, match="unsupported"):
        DiscordEvent.from_payload("PRESENCE_UPDATE", {"channel_id": "1"})


def test_channel_allowlist_requires_explicit_scope():
    with pytest.raises(ValueError, match="required"):
        parse_channel_allowlist("")
    assert parse_channel_allowlist("10, 20") == {"10", "20"}
    assert parse_channel_allowlist("*") is None


def test_discord_event_schema_is_valid_json():
    schema_path = Path(__file__).parents[3] / "schemas" / "DiscordEvent.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["title"] == "DiscordEvent"
    assert "MESSAGE_DELETE" in schema["properties"]["event_type"]["enum"]


def test_store_is_idempotent(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    event = DiscordEvent.from_payload("MESSAGE_CREATE", message_payload("100", "hello"))
    assert store.append(event) is True
    assert store.append(event) is False
    assert store.last_sequence() == 1


def test_projector_replays_update_and_delete(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append(DiscordEvent.from_payload("MESSAGE_CREATE", message_payload("100", "old")))
    store.append(
        DiscordEvent.from_payload(
            "MESSAGE_UPDATE",
            {
                "id": "100",
                "channel_id": "10",
                "guild_id": "1",
                "content": "new",
                "edited_timestamp": "2026-07-29T01:26:00+09:00",
            },
        )
    )
    store.append(DiscordEvent.from_payload("MESSAGE_CREATE", message_payload("101", "delete me")))
    store.append(
        DiscordEvent.from_payload(
            "MESSAGE_DELETE",
            {"id": "101", "channel_id": "10", "guild_id": "1"},
        )
    )

    projection = DiscordProjector(store, tmp_path / "wiki").render()

    assert [message.message_id for message in projection.messages] == ["100"]
    assert projection.messages[0].content == "new"
    channel = tmp_path / "wiki" / "discord" / "channels" / "backend--10.md"
    text = channel.read_text(encoding="utf-8")
    assert "new" in text
    assert "delete me" not in text
    assert "`discord:10:100`" in text


def test_projector_preserves_reply_and_attachment(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    payload = message_payload("101", "see file", reply_to="100")
    payload["attachments"] = [
        {"id": "9", "filename": "design.pdf", "url": "https://cdn.example/design.pdf"}
    ]
    store.append(DiscordEvent.from_payload("MESSAGE_CREATE", payload))
    DiscordProjector(store, tmp_path / "wiki").render()
    text = (
        tmp_path / "wiki" / "discord" / "channels" / "backend--10.md"
    ).read_text(encoding="utf-8")
    assert "Replying to message `100`" in text
    assert "[design.pdf](https://cdn.example/design.pdf)" in text


def test_raw_jsonl_can_rebuild_source_events(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append(DiscordEvent.from_payload("MESSAGE_CREATE", message_payload("100", "hello")))
    DiscordProjector(store, tmp_path / "wiki").render()
    raw_path = tmp_path / "wiki" / "discord" / "raw" / "events.jsonl"
    row = json.loads(raw_path.read_text(encoding="utf-8"))
    assert row["sequence"] == 1
    assert row["payload"]["content"] == "hello"


def test_rest_paginates_with_before_and_preserves_each_page():
    calls = []
    first_page = [
        {"id": str(value), "channel_id": "10", "content": str(value)}
        for value in range(200, 100, -1)
    ]
    second_page = [
        {"id": "100", "channel_id": "10", "content": "100"},
        {"id": "99", "channel_id": "10", "content": "99"},
    ]

    def request_json(path, params):
        calls.append((path, dict(params)))
        return first_page if "before" not in params else second_page

    client = DiscordRestClient("token", request_json=request_json)
    messages = list(client.iter_channel_messages("10"))
    assert messages[0]["id"] == "101"
    assert messages[99]["id"] == "200"
    assert messages[-2]["id"] == "99"
    assert messages[-1]["id"] == "100"
    assert calls == [
        ("/channels/10/messages", {"limit": "100"}),
        ("/channels/10/messages", {"limit": "100", "before": "101"}),
    ]


def test_backfill_is_idempotent(tmp_path):
    def request_json(path, params):
        if path.endswith("/channels"):
            return [{"id": "10", "name": "backend", "type": 0}]
        if path.endswith("/threads/active"):
            return {"threads": []}
        if path.endswith("/threads/archived/public"):
            return {"threads": [], "has_more": False}
        return [message_payload("100", "hello")] if "before" not in params else []

    store = EventStore(tmp_path / "events.sqlite3")
    client = DiscordRestClient("token", request_json=request_json)
    assert client.backfill_guild("1", store) == 1
    assert client.backfill_guild("1", store) == 0


def test_backfill_includes_active_and_archived_public_threads(tmp_path):
    def request_json(path, params):
        if path.endswith("/channels"):
            return [{"id": "20", "name": "research", "type": 15}]
        if path.endswith("/threads/active"):
            return {
                "threads": [
                    {"id": "21", "name": "active-topic", "type": 11, "parent_id": "20"}
                ]
            }
        if path.endswith("/threads/archived/public"):
            return {
                "threads": [
                    {
                        "id": "22",
                        "name": "archived-topic",
                        "type": 11,
                        "parent_id": "20",
                        "thread_metadata": {
                            "archive_timestamp": "2026-07-01T00:00:00+00:00"
                        },
                    }
                ],
                "has_more": False,
            }
        channel_id = path.split("/")[2]
        return [message_payload(f"100{channel_id}", channel_id, channel_id=channel_id)]

    store = EventStore(tmp_path / "events.sqlite3")
    imported = DiscordRestClient("token", request_json=request_json).backfill_guild("1", store)
    assert imported == 2
    assert {event.channel_id for _, event in store.iter_events()} == {"21", "22"}


def test_backfill_respects_parent_channel_allowlist(tmp_path):
    def request_json(path, params):
        if path.endswith("/channels"):
            return [
                {"id": "10", "name": "allowed", "type": 0},
                {"id": "20", "name": "blocked", "type": 0},
            ]
        if path.endswith("/threads/active"):
            return {"threads": []}
        if path.endswith("/threads/archived/public"):
            return {"threads": [], "has_more": False}
        channel_id = path.split("/")[2]
        return [message_payload(channel_id, channel_id, channel_id=channel_id)]

    store = EventStore(tmp_path / "events.sqlite3")
    imported = DiscordRestClient("token", request_json=request_json).backfill_guild(
        "1",
        store,
        allowed_channel_ids={"10"},
    )
    assert imported == 1
    assert [event.channel_id for _, event in store.iter_events()] == ["10"]


def test_search_returns_stable_discord_citation(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append(
        DiscordEvent.from_payload(
            "MESSAGE_CREATE",
            message_payload("100", "Separate the conversion worker from the API"),
        )
    )
    service = DiscordMemoryService(store, tmp_path / "wiki")
    hits = service.search("conversion worker")
    assert hits[0].citation == "discord:10:100"
    assert "conversion worker" in hits[0].content


def test_search_prefers_recent_message_at_equal_score(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append(
        DiscordEvent.from_payload(
            "MESSAGE_CREATE",
            message_payload("100", "worker", timestamp="2026-07-28T01:00:00+09:00"),
        )
    )
    store.append(
        DiscordEvent.from_payload(
            "MESSAGE_CREATE",
            message_payload("101", "worker", timestamp="2026-07-29T01:00:00+09:00"),
        )
    )
    hits = DiscordMemoryService(store, tmp_path / "wiki").search("worker")
    assert [hit.citation for hit in hits] == ["discord:10:101", "discord:10:100"]


class FakeSummaryProvider:
    def __init__(self):
        self.calls = []

    def summarize(
        self,
        previous_summary,
        new_messages,
        retrieved_context,
        *,
        safety_identifier=None,
    ):
        self.calls.append((previous_summary, list(new_messages), safety_identifier))
        return """# Current Project State

## Executive Summary
Worker split discussed.

## Decisions Made
- [DEC-001] Separate the worker. `discord:10:100`

## Active Tasks
- [ ] Implement worker split.

## Unresolved Questions
- Queue choice?

## Architecture Changes
- Worker boundary.

## Important Links and Files
- None.

## Member Contributions
- Mingoomato proposed the split.

## Recent Activity
- Worker discussion.
"""


def test_summary_is_incremental_and_writes_structured_views(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append(
        DiscordEvent.from_payload(
            "MESSAGE_CREATE",
            message_payload("100", "Separate the conversion worker"),
        )
    )
    service = DiscordMemoryService(store, tmp_path / "wiki")
    provider = FakeSummaryProvider()

    summary = service.refresh_summary(provider)
    repeated = service.refresh_summary(provider)

    assert "DEC-001" in summary
    assert repeated == summary + "\n"
    assert len(provider.calls) == 1
    assert "discord:10:100" in provider.calls[0][1][0]
    assert (tmp_path / "wiki" / "summaries" / "decisions.md").exists()
    assert service.section("Active Tasks") == "- [ ] Implement worker split."


def test_delete_only_batch_advances_summary_checkpoint(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append(
        DiscordEvent.from_payload("MESSAGE_CREATE", message_payload("100", "temporary"))
    )
    service = DiscordMemoryService(store, tmp_path / "wiki")
    first_provider = FakeSummaryProvider()
    service.refresh_summary(first_provider)
    store.append(
        DiscordEvent.from_payload(
            "MESSAGE_DELETE",
            {"id": "100", "channel_id": "10", "guild_id": "1"},
        )
    )
    second_provider = FakeSummaryProvider()
    service.refresh_summary(second_provider)
    assert "message deleted" in second_provider.calls[0][1][0]
    assert store.get_metadata("summary_sequence") == "2"


def test_openai_provider_builds_low_cost_responses_request():
    captured = {}

    def request_json(payload):
        captured.update(payload)
        return {"output_text": "# Current Project State"}

    provider = OpenAIResponsesSummarizer("key", request_json=request_json)
    result = provider.summarize("old", ["new"], [], safety_identifier="safe")
    assert result == "# Current Project State"
    assert captured["model"] == "gpt-5.6-luna"
    assert captured["reasoning"] == {"effort": "low"}
    assert captured["store"] is False
    assert captured["safety_identifier"] == "safe"


def test_openai_provider_extracts_message_output():
    response = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "memory"}],
            }
        ]
    }
    assert OpenAIResponsesSummarizer.extract_text(response) == "memory"


def test_openai_provider_rejects_empty_output():
    with pytest.raises(ValueError, match="no text"):
        OpenAIResponsesSummarizer.extract_text({"output": []})
