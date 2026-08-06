"""Persistent hardware profiles, one per Discord member.

Butin and Rubin both read the screen. Which means a bug report is nearly
useless without the resolution, the Windows display scaling and the game's
display mode: the same build behaves differently at 1920x1080 100% and at
2560x1440 150%. Asking for it once and reusing it on every later report is the
whole point of this module.

SQLite through :mod:`aiosqlite`, one small table. The database path is
configurable so tests run entirely in memory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from pathlib import Path

import aiosqlite

log = logging.getLogger("discord-bdo.profiles")

DEFAULT_PATH = Path("data") / "profiles.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    user_id      INTEGER PRIMARY KEY,
    display_name TEXT    NOT NULL DEFAULT '',
    resolution   TEXT    NOT NULL DEFAULT '',
    scaling      TEXT    NOT NULL DEFAULT '',
    display_mode TEXT    NOT NULL DEFAULT '',
    game_language TEXT   NOT NULL DEFAULT '',
    hardware     TEXT    NOT NULL DEFAULT '',
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


@dataclass(frozen=True)
class Profile:
    user_id: int
    display_name: str = ""
    #: Screen resolution as typed, e.g. "2560x1440".
    resolution: str = ""
    #: Windows display scaling, e.g. "150%".
    scaling: str = ""
    #: Fullscreen / borderless / windowed, as typed.
    display_mode: str = ""
    #: In-game language, which drives which OCR dictionary applies.
    game_language: str = ""
    #: Free text: CPU, GPU, RAM.
    hardware: str = ""
    updated_at: str = ""

    def as_lines(self) -> list[str]:
        """Human-readable rows, skipping anything left blank."""
        labels = (
            ("resolution", "Résolution / Resolution"),
            ("scaling", "Échelle Windows / Scaling"),
            ("display_mode", "Affichage du jeu / Display mode"),
            ("game_language", "Langue du jeu / Game language"),
            ("hardware", "Matériel / Hardware"),
        )
        return [
            f"**{label}** : {getattr(self, attr)}"
            for attr, label in labels
            if getattr(self, attr)
        ]

    def as_markdown_table(self) -> str:
        """Compact table for a GitHub issue body."""
        rows = [
            ("Resolution", self.resolution),
            ("Scaling", self.scaling),
            ("Display mode", self.display_mode),
            ("Game language", self.game_language),
            ("Hardware", self.hardware),
        ]
        kept = [(name, value) for name, value in rows if value]
        if not kept:
            return ""
        lines = ["| | |", "|---|---|"]
        lines += [f"| {name} | {value} |" for name, value in kept]
        return "\n".join(lines)

    @property
    def is_empty(self) -> bool:
        return not any(
            (self.resolution, self.scaling, self.display_mode, self.game_language, self.hardware)
        )


class ProfileStore:
    """Tiny async key-value store over SQLite.

    ``path`` accepts ``":memory:"`` for tests. Every call opens and closes its
    own connection: the traffic here is a handful of writes per day, and a
    short-lived connection cannot go stale behind a long-running bot.
    """

    def __init__(self, path: Path | str = DEFAULT_PATH) -> None:
        self.path = path
        self._memory: aiosqlite.Connection | None = None

    @property
    def in_memory(self) -> bool:
        return str(self.path) == ":memory:"

    async def connect(self) -> aiosqlite.Connection:
        if self.in_memory:
            # A fresh :memory: connection would be a fresh empty database, so
            # the same one is kept alive for the lifetime of the store.
            if self._memory is None:
                self._memory = await aiosqlite.connect(":memory:")
                await self._memory.executescript(SCHEMA)
                await self._memory.commit()
            return self._memory
        return await aiosqlite.connect(self.path)

    async def setup(self) -> None:
        if not self.in_memory:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        connection = await self.connect()
        try:
            await connection.executescript(SCHEMA)
            await connection.commit()
        finally:
            if not self.in_memory:
                await connection.close()

    async def close(self) -> None:
        if self._memory is not None:
            await self._memory.close()
            self._memory = None

    async def save(self, profile: Profile) -> None:
        connection = await self.connect()
        try:
            await connection.execute(
                """
                INSERT INTO profiles
                    (user_id, display_name, resolution, scaling, display_mode,
                     game_language, hardware, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    resolution   = excluded.resolution,
                    scaling      = excluded.scaling,
                    display_mode = excluded.display_mode,
                    game_language= excluded.game_language,
                    hardware     = excluded.hardware,
                    updated_at   = datetime('now')
                """,
                (
                    profile.user_id,
                    profile.display_name,
                    profile.resolution,
                    profile.scaling,
                    profile.display_mode,
                    profile.game_language,
                    profile.hardware,
                ),
            )
            await connection.commit()
        finally:
            if not self.in_memory:
                await connection.close()

    async def get(self, user_id: int) -> Profile | None:
        connection = await self.connect()
        try:
            connection.row_factory = aiosqlite.Row
            async with connection.execute(
                "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
        finally:
            if not self.in_memory:
                await connection.close()
        if row is None:
            return None
        known = {f.name for f in fields(Profile)}
        return Profile(**{k: row[k] for k in row.keys() if k in known})

    async def count(self) -> int:
        connection = await self.connect()
        try:
            async with connection.execute("SELECT COUNT(*) FROM profiles") as cursor:
                (total,) = await cursor.fetchone()
        finally:
            if not self.in_memory:
                await connection.close()
        return int(total)

    async def delete(self, user_id: int) -> bool:
        connection = await self.connect()
        try:
            cursor = await connection.execute(
                "DELETE FROM profiles WHERE user_id = ?", (user_id,)
            )
            await connection.commit()
            return cursor.rowcount > 0
        finally:
            if not self.in_memory:
                await connection.close()


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #

#: Common ways people write a resolution, mapped to the canonical form.
_RESOLUTION_SEPARATORS = ("x", "X", "*", "×", " par ", " by ")


def normalise_resolution(raw: str) -> str:
    """Turn "2560 * 1440", "2560×1440" or "2560 par 1440" into "2560x1440".

    Left untouched when it does not look like two numbers, because a made-up
    value is worse than the user's own words.
    """
    text = raw.strip()
    if not text:
        return ""
    for separator in _RESOLUTION_SEPARATORS:
        if separator in text:
            left, _, right = text.partition(separator)
            width, height = left.strip(), right.strip()
            if width.isdigit() and height.isdigit():
                return f"{width}x{height}"
            break
    return text


def normalise_scaling(raw: str) -> str:
    """Accept "150", "150%", "1.5" and return "150%"."""
    text = raw.strip().replace(",", ".")
    if not text:
        return ""
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        value = float(text)
    except ValueError:
        return raw.strip()
    # Someone typing 1.5 means 150%, someone typing 150 already means 150%.
    if value <= 5:
        value *= 100
    if value.is_integer():
        return f"{int(value)}%"
    return f"{value:g}%"
