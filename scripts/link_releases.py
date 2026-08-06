"""Wire GitHub releases into the Discord release channels.

This needs no bot: Discord understands GitHub's webhook payload natively when
the delivery URL ends with ``/github``. One webhook per repository, listening
to release events only, so a push storm never floods the server.

    python scripts/link_releases.py \
        --butin https://discord.com/api/webhooks/... \
        --rubin https://discord.com/api/webhooks/...

Add ``--dry-run`` to see what would be sent without creating anything.
Requires GITHUB_TOKEN (scope ``repo``, or fine-grained ``Webhooks: write``).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import blueprint as bp  # noqa: E402

API_ROOT = "https://api.github.com"
#: Only these events reach Discord. Adding "push" here would post every commit.
EVENTS = ["release"]


def discord_delivery_url(webhook_url: str) -> str:
    """Discord parses GitHub payloads only on the /github variant of the URL."""
    url = webhook_url.strip().rstrip("/")
    if not url.startswith("https://discord.com/api/webhooks/") and not url.startswith(
        "https://discordapp.com/api/webhooks/"
    ):
        raise ValueError(f"pas une URL de webhook Discord : {url[:60]}")
    if url.endswith("/github"):
        return url
    return url + "/github"


def request(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{API_ROOT}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "discord-bdo",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        body = response.read().decode()
    return json.loads(body) if body else {}


def existing_hook(repo: str, token: str, delivery_url: str) -> dict | None:
    """Find a webhook already pointing at this URL, so reruns are harmless."""
    try:
        hooks = request("GET", f"/repos/{repo}/hooks", token)
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            f"Lecture des webhooks de {repo} refusée ({exc.code}). "
            "Le jeton a-t-il la portée 'repo' / 'Webhooks: write' ?"
        ) from exc
    for hook in hooks:
        if hook.get("config", {}).get("url") == delivery_url:
            return hook
    return None


def create_hook(repo: str, token: str, delivery_url: str) -> dict:
    return request(
        "POST",
        f"/repos/{repo}/hooks",
        token,
        {
            "name": "web",
            "active": True,
            "events": EVENTS,
            "config": {
                "url": delivery_url,
                "content_type": "json",
                "insecure_ssl": "0",
            },
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for product in bp.PRODUCTS:
        parser.add_argument(
            f"--{product.slug}",
            metavar="URL",
            help=f"URL du webhook Discord du salon {product.slug}-versions-releases",
        )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token and not args.dry_run:
        print("GITHUB_TOKEN manquant.", file=sys.stderr)
        return 2

    asked = 0
    for product in bp.PRODUCTS:
        raw = getattr(args, product.slug, None)
        if not raw:
            continue
        asked += 1
        try:
            delivery = discord_delivery_url(raw)
        except ValueError as exc:
            print(f"{product.label} : {exc}", file=sys.stderr)
            return 2

        if args.dry_run:
            print(f"{product.label} : créerait un webhook {EVENTS} sur {product.repo}")
            continue

        if existing_hook(product.repo, token, delivery):
            print(f"{product.label} : webhook déjà en place sur {product.repo}, rien à faire.")
            continue

        try:
            hook = create_hook(product.repo, token, delivery)
        except urllib.error.HTTPError as exc:
            print(
                f"{product.label} : création refusée ({exc.code}) — {exc.read().decode()[:200]}",
                file=sys.stderr,
            )
            return 1
        print(f"{product.label} : webhook #{hook.get('id')} créé sur {product.repo}.")

    if asked == 0:
        parser.print_help()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
