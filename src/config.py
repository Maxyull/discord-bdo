"""Configuration loaded from the environment.

Every secret comes from the environment (or a local ``.env``); nothing
sensitive is ever written to this repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv is optional in production (the VPS injects real env vars)
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - exercised only without the package
    def load_dotenv(*_args, **_kwargs):  # type: ignore[misc]
        return False


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    """Raised when a required setting is missing or malformed."""


def _get_int(name: str, *, required: bool = False) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        if required:
            raise ConfigError(
                f"{name} manquant. Copiez .env.example vers .env et remplissez-le."
            )
        return None
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name} doit être un nombre entier, reçu {raw!r}.") from None


def _get_str(name: str, *, required: bool = False, default: str = "") -> str:
    raw = os.environ.get(name, "").strip()
    if not raw:
        if required:
            raise ConfigError(
                f"{name} manquant. Copiez .env.example vers .env et remplissez-le."
            )
        return default
    return raw


@dataclass(frozen=True)
class Config:
    discord_token: str
    guild_id: int | None
    github_token: str
    github_default_labels: tuple[str, ...]
    log_level: str
    #: When true the bot never writes to GitHub, it only logs what it would do.
    dry_run: bool

    @property
    def github_enabled(self) -> bool:
        return bool(self.github_token)


def load(env_file: Path | str | None = None, *, require_token: bool = True) -> Config:
    """Read the configuration.

    ``require_token`` is turned off by the test suite and by ``--check`` runs
    that only validate the blueprint.
    """
    path = Path(env_file) if env_file else PROJECT_ROOT / ".env"
    if path.is_file():
        load_dotenv(path, override=False)

    labels = _get_str("GITHUB_DEFAULT_LABELS", default="discord")
    return Config(
        discord_token=_get_str("DISCORD_TOKEN", required=require_token),
        guild_id=_get_int("DISCORD_GUILD_ID"),
        github_token=_get_str("GITHUB_TOKEN"),
        github_default_labels=tuple(
            part.strip() for part in labels.split(",") if part.strip()
        ),
        log_level=_get_str("LOG_LEVEL", default="INFO").upper(),
        dry_run=_get_str("DRY_RUN", default="0") in {"1", "true", "yes", "oui"},
    )
