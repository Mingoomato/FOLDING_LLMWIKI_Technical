"""Discord REST historical importer with explicit pagination and rate limits."""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Iterator
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import DiscordEvent
from .store import EventStore


JsonRequest = Callable[[str, dict[str, str]], Any]


class DiscordRestClient:
    API_BASE = "https://discord.com/api/v10"

    def __init__(
        self,
        token: str,
        *,
        request_json: JsonRequest | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not token:
            raise ValueError("Discord bot token is required")
        self.token = token
        self._request_override = request_json
        self._sleep = sleep

    def _request_json(self, path: str, params: dict[str, str]) -> Any:
        if self._request_override:
            return self._request_override(path, params)
        query = f"?{urlencode(params)}" if params else ""
        request = Request(
            f"{self.API_BASE}{path}{query}",
            headers={
                "Authorization": f"Bot {self.token}",
                "User-Agent": "DiscordBot (https://github.com/Mingoomato/FOLDING_LLMWIKI_Technical, 1.0)",
            },
        )
        while True:
            try:
                with urlopen(request, timeout=30) as response:
                    return json.load(response)
            except HTTPError as error:
                if error.code != 429:
                    raise
                body = json.loads(error.read().decode("utf-8"))
                self._sleep(float(body.get("retry_after", 1.0)))

    def guild_channels(self, guild_id: str) -> list[dict[str, Any]]:
        channels = self._request_json(f"/guilds/{guild_id}/channels", {})
        return [channel for channel in channels if channel.get("type") in {0, 5, 15, 16}]

    def active_threads(self, guild_id: str) -> list[dict[str, Any]]:
        response = self._request_json(f"/guilds/{guild_id}/threads/active", {})
        return list(response.get("threads") or [])

    def archived_public_threads(self, channel_id: str) -> Iterator[dict[str, Any]]:
        before = None
        while True:
            params = {"limit": "100"}
            if before:
                params["before"] = before
            response = self._request_json(
                f"/channels/{channel_id}/threads/archived/public",
                params,
            )
            threads = list(response.get("threads") or [])
            yield from threads
            if not response.get("has_more") or not threads:
                return
            before = str(threads[-1]["thread_metadata"]["archive_timestamp"])

    def iter_channel_messages(self, channel_id: str) -> Iterator[dict[str, Any]]:
        before = None
        while True:
            params = {"limit": "100"}
            if before:
                params["before"] = before
            page = self._request_json(f"/channels/{channel_id}/messages", params)
            if not page:
                return
            for message in reversed(page):
                yield message
            before = str(page[-1]["id"])
            if len(page) < 100:
                return

    def backfill_guild(
        self,
        guild_id: str,
        store: EventStore,
        *,
        allowed_channel_ids: set[str] | None = None,
    ) -> int:
        imported = 0
        parent_channels = self.guild_channels(guild_id)
        if allowed_channel_ids is not None:
            parent_channels = [
                channel
                for channel in parent_channels
                if str(channel["id"]) in allowed_channel_ids
            ]
        thread_by_id = {
            str(thread["id"]): thread
            for thread in self.active_threads(guild_id)
            if allowed_channel_ids is None
            or str(thread["id"]) in allowed_channel_ids
            or str(thread.get("parent_id") or "") in allowed_channel_ids
        }
        for parent in parent_channels:
            for thread in self.archived_public_threads(str(parent["id"])):
                thread_by_id[str(thread["id"])] = thread

        source_channels = [
            channel for channel in parent_channels if channel.get("type") in {0, 5}
        ] + list(thread_by_id.values())
        for channel in source_channels:
            channel_id = str(channel["id"])
            for message in self.iter_channel_messages(channel_id):
                message["guild_id"] = guild_id
                message["channel_id"] = channel_id
                message["_llmwiki"] = {
                    "channel_name": channel.get("name") or channel_id,
                    "thread_id": channel_id if channel.get("type") in {10, 11, 12} else None,
                    "thread_name": channel.get("name") if channel.get("type") in {10, 11, 12} else None,
                }
                event = DiscordEvent.from_payload("MESSAGE_CREATE", message)
                imported += int(store.append(event))
        return imported
