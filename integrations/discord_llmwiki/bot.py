"""Optional discord.py Gateway and slash-command adapter."""
from __future__ import annotations

import os
from pathlib import Path

from .models import DiscordEvent
from .openai_provider import OpenAIResponsesSummarizer
from .policy import channel_allowed, parse_channel_allowlist
from .projector import DiscordProjector
from .service import DiscordMemoryService
from .store import EventStore


def run_bot(data_root: str | Path) -> None:
    try:
        import discord
        from discord import app_commands
    except ImportError as error:
        raise RuntimeError("Install integrations/discord_llmwiki/requirements.txt") from error

    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is required")
    allowlist = parse_channel_allowlist(
        os.environ.get("DISCORD_CHANNEL_ALLOWLIST", "")
    )
    allowed_runtime_channels = None if allowlist is None else set(allowlist)

    root = Path(data_root)
    store = EventStore(root / "discord-events.sqlite3")
    projector = DiscordProjector(store, root)
    service = DiscordMemoryService(store, root)

    intents = discord.Intents.none()
    intents.guilds = True
    intents.guild_messages = True
    intents.message_content = True

    class LLMWikiClient(discord.Client):
        def __init__(self):
            super().__init__(intents=intents)
            self.tree = app_commands.CommandTree(self)

        async def setup_hook(self):
            await self.tree.sync()

    client = LLMWikiClient()

    def message_payload(message) -> dict:
        payload = {
            "id": str(message.id),
            "guild_id": str(message.guild.id) if message.guild else None,
            "channel_id": str(message.channel.id),
            "timestamp": message.created_at.isoformat(),
            "edited_timestamp": message.edited_at.isoformat() if message.edited_at else None,
            "content": message.content,
            "author": {
                "id": str(message.author.id),
                "username": message.author.name,
                "global_name": message.author.display_name,
            },
            "attachments": [
                {
                    "id": str(attachment.id),
                    "filename": attachment.filename,
                    "url": attachment.url,
                    "content_type": attachment.content_type,
                    "size": attachment.size,
                }
                for attachment in message.attachments
            ],
            "_llmwiki": {
                "channel_name": getattr(message.channel, "name", str(message.channel.id)),
                "thread_id": str(message.channel.id) if isinstance(message.channel, discord.Thread) else None,
                "thread_name": message.channel.name if isinstance(message.channel, discord.Thread) else None,
            },
        }
        if message.reference and message.reference.message_id:
            payload["message_reference"] = {"message_id": str(message.reference.message_id)}
        return payload

    @client.event
    async def on_message(message):
        if message.author == client.user or not channel_allowed(message.channel, allowlist):
            return
        if allowed_runtime_channels is not None:
            allowed_runtime_channels.add(str(message.channel.id))
        store.append(DiscordEvent.from_payload("MESSAGE_CREATE", message_payload(message)))
        projector.render()

    @client.event
    async def on_message_edit(before, after):
        if not channel_allowed(after.channel, allowlist):
            return
        store.append(DiscordEvent.from_payload("MESSAGE_UPDATE", message_payload(after)))
        projector.render()

    @client.event
    async def on_raw_message_delete(payload):
        if (
            allowed_runtime_channels is not None
            and str(payload.channel_id) not in allowed_runtime_channels
        ):
            return
        store.append(
            DiscordEvent.from_payload(
                "MESSAGE_DELETE",
                {
                    "id": str(payload.message_id),
                    "channel_id": str(payload.channel_id),
                    "guild_id": str(payload.guild_id) if payload.guild_id else None,
                },
            )
        )
        projector.render()

    @client.event
    async def on_thread_create(thread):
        if not channel_allowed(thread, allowlist):
            return
        if allowed_runtime_channels is not None:
            allowed_runtime_channels.add(str(thread.id))
        store.append(
            DiscordEvent.from_payload(
                "THREAD_CREATE",
                {
                    "id": str(thread.id),
                    "guild_id": str(thread.guild.id),
                    "name": thread.name,
                    "parent_id": str(thread.parent_id),
                },
            )
        )

    @client.event
    async def on_thread_update(before, after):
        if not channel_allowed(after, allowlist):
            return
        store.append(
            DiscordEvent.from_payload(
                "THREAD_UPDATE",
                {
                    "id": str(after.id),
                    "guild_id": str(after.guild.id),
                    "name": after.name,
                    "parent_id": str(after.parent_id),
                },
            )
        )

    @client.event
    async def on_thread_delete(thread):
        if not channel_allowed(thread, allowlist):
            return
        store.append(
            DiscordEvent.from_payload(
                "THREAD_DELETE",
                {
                    "id": str(thread.id),
                    "guild_id": str(thread.guild.id),
                    "name": thread.name,
                    "parent_id": str(thread.parent_id),
                },
            )
        )

    @client.tree.command(name="context", description="Search indexed Discord evidence")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def context(interaction, query: str):
        await interaction.response.send_message(service.context_markdown(query)[:1900])

    @client.tree.command(name="decisions", description="Show recorded project decisions")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def decisions(interaction):
        await interaction.response.send_message(service.section("Decisions Made")[:1900])

    @client.tree.command(name="tasks", description="Show active project tasks")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def tasks(interaction):
        await interaction.response.send_message(service.section("Active Tasks")[:1900])

    @client.tree.command(name="summary", description="Refresh and show project memory")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def summary(interaction):
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            await interaction.response.send_message("OPENAI_API_KEY is not configured.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        provider = OpenAIResponsesSummarizer(
            api_key,
            model=os.environ.get("OPENAI_MODEL", "gpt-5.6-luna"),
        )
        result = service.refresh_summary(provider)
        await interaction.followup.send(result[:1900])

    @client.tree.command(name="export-md", description="Export projected Discord Markdown")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def export_markdown(interaction):
        path = service.export_markdown()
        await interaction.response.send_message(file=discord.File(path))

    client.run(token)
