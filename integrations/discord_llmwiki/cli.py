"""Command-line entry point for backfill, projection, search, and bot mode."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from .bot import run_bot
from .openai_provider import OpenAIResponsesSummarizer
from .policy import parse_channel_allowlist
from .projector import DiscordProjector
from .rest import DiscordRestClient
from .service import DiscordMemoryService
from .store import EventStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="discord-llmwiki")
    parser.add_argument(
        "--data-root",
        default=os.environ.get("LLMWIKI_DISCORD_ROOT", ".llmwiki-discord"),
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("init")

    backfill = subcommands.add_parser("backfill")
    backfill.add_argument("--guild-id", required=True)

    subcommands.add_parser("project")
    search = subcommands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    subcommands.add_parser("summarize")
    subcommands.add_parser("run-bot")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.data_root)
    store = EventStore(root / "discord-events.sqlite3")
    projector = DiscordProjector(store, root)
    service = DiscordMemoryService(store, root)

    if args.command == "init":
        projector.render()
        return 0
    if args.command == "backfill":
        token = os.environ.get("DISCORD_BOT_TOKEN", "")
        allowlist = parse_channel_allowlist(
            os.environ.get("DISCORD_CHANNEL_ALLOWLIST", "")
        )
        imported = DiscordRestClient(token).backfill_guild(
            args.guild_id,
            store,
            allowed_channel_ids=allowlist,
        )
        projector.render()
        print(f"imported {imported} events")
        return 0
    if args.command == "project":
        projection = projector.render()
        print(f"projected {len(projection.messages)} active messages")
        return 0
    if args.command == "search":
        print(service.context_markdown(args.query, limit=args.limit))
        return 0
    if args.command == "summarize":
        provider = OpenAIResponsesSummarizer(
            os.environ.get("OPENAI_API_KEY", ""),
            model=os.environ.get("OPENAI_MODEL", "gpt-5.6-luna"),
        )
        print(service.refresh_summary(provider))
        return 0
    if args.command == "run-bot":
        run_bot(root)
        return 0
    return 2
