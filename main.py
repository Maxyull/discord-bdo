"""Command line entry point.

    python main.py             run the bot (this is what the VPS runs)
    python main.py --setup     run the bot just long enough to build the server
    python main.py --check     validate the blueprint offline, no token needed
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from src import blueprint as bp
from src import guides
from src import setup_guild
from src.bot import BdoBot
from src.config import ConfigError, load


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("discord").setLevel(logging.WARNING)


def check_blueprint() -> int:
    """Offline sanity pass, so a typo is caught before touching a live server."""
    problems: list[str] = []

    keys = [ch.key for _, ch in bp.all_channel_specs() if ch.key]
    duplicates = {k for k in keys if keys.count(k) > 1}
    if duplicates:
        problems.append(f"clés de salon en double : {', '.join(sorted(duplicates))}")

    names = [setup_guild.normalise(ch.name) for _, ch in bp.all_channel_specs()]
    dup_names = {n for n in names if names.count(n) > 1}
    if dup_names:
        problems.append(f"noms de salon en double : {', '.join(sorted(dup_names))}")

    declared = bp.channel_keys()
    for product in bp.PRODUCTS:
        for attr in (
            "help_channel_key",
            "bug_channel_key",
            "idea_channel_key",
            "release_channel_key",
        ):
            key = getattr(product, attr)
            if key not in declared:
                problems.append(f"{product.slug}.{attr} pointe vers {key!r}, absent du plan")

    # A beta channel without the Tester role would be visible to nobody but
    # staff, which looks like a permission bug rather than a missing role.
    role_names = {spec.name for spec in bp.ROLES}
    uses_beta = any(
        setup_guild.effective_access(cat, ch)
        in (bp.Access.BETA_ONLY, bp.Access.BETA_READ_ONLY)
        for cat, ch in bp.all_channel_specs()
    )
    if uses_beta and bp.ROLE_TESTER not in role_names:
        problems.append(f"des salons exigent le rôle {bp.ROLE_TESTER!r}, absent de ROLES")

    problems.extend(guides.check())

    total = len(list(bp.all_channel_specs()))
    print(f"Plan : {len(bp.CATEGORIES)} catégories, {total} salons, {len(bp.ROLES)} rôles.")
    print("Rôles, du haut vers le bas : " + " > ".join(r.name for r in bp.ROLES))
    print()
    for cat in bp.CATEGORIES:
        print(f"  {cat.name}")
        for ch in cat.channels:
            marker = {"text": "#", "forum": "▤", "voice": "🔊"}[ch.kind.value]
            # The effective access, not the declared one: a channel left at the
            # PUBLIC default inside a private category is not public.
            access = setup_guild.effective_access(cat, ch)
            print(f"    {marker} {ch.name}  [{access.value}]")

    if problems:
        print("\nProblèmes :", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"\n{len(guides.GUIDES)} guides prêts à être publiés dans le forum.")
    print("Plan valide.")
    return 0


async def run_bot(*, setup_then_exit: bool) -> int:
    config = load()
    configure_logging(config.log_level)
    bot = BdoBot(config)

    if not setup_then_exit:
        await bot.start(config.discord_token)
        return 0

    ready = asyncio.Event()
    result = {"code": 0}

    @bot.event
    async def on_ready() -> None:  # noqa: F811 - replaces the class handler on purpose
        try:
            targets = (
                [g for g in bot.guilds if g.id == config.guild_id]
                if config.guild_id
                else list(bot.guilds)
            )
            if not targets:
                logging.error(
                    "Le bot n'est sur aucun serveur correspondant. "
                    "Invitez-le, ou corrigez DISCORD_GUILD_ID."
                )
                result["code"] = 1
                return
            for guild in targets:
                logging.info("setting up %s", guild.name)
                try:
                    report = await setup_guild.run(guild, post_panels=bot.post_panels)
                except setup_guild.PermissionsMissing as missing:
                    print(
                        "Droits insuffisants sur "
                        f"{guild.name}, rien n'a été touché :",
                        file=sys.stderr,
                    )
                    for problem in missing.problems:
                        print(f"  {problem}", file=sys.stderr)
                    print(
                        "\nDonnez au bot un rôle Administrateur placé tout en haut "
                        "de la liste des rôles, puis relancez.",
                        file=sys.stderr,
                    )
                    result["code"] = 1
                    continue
                print(report.summary())
        except Exception:
            logging.exception("setup failed")
            result["code"] = 1
        finally:
            ready.set()

    async with bot:
        asyncio.create_task(bot.start(config.discord_token))
        await ready.wait()
        await bot.close()
    return result["code"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Discord bot for Butin and Rubin")
    parser.add_argument(
        "--setup", action="store_true", help="build the server, then exit"
    )
    parser.add_argument(
        "--check", action="store_true", help="validate the blueprint offline"
    )
    args = parser.parse_args()

    if args.check:
        return check_blueprint()

    try:
        return asyncio.run(run_bot(setup_then_exit=args.setup))
    except ConfigError as exc:
        print(f"Configuration : {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
