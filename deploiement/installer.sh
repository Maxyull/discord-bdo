#!/usr/bin/env bash
# Install or update discord-bdo on the VPS, under /opt/discordbot/<bot>/.
#
#   sudo bash deploiement/installer.sh
#
# Idempotent: run it again to deploy a new version. It never touches the .env,
# so the token survives every update.
set -euo pipefail

BOT_NAME="discord-bdo"
BASE="/opt/discordbot"
TARGET="${BASE}/${BOT_NAME}"
REPO="https://github.com/Maxyull/discord-bdo.git"
SERVICE="${BOT_NAME}.service"
RUN_USER="discordbot"

if [[ $EUID -ne 0 ]]; then
  echo "À lancer en root : sudo bash $0" >&2
  exit 1
fi

# One shared, unprivileged account for every bot under /opt/discordbot.
if ! id -u "${RUN_USER}" >/dev/null 2>&1; then
  echo "== création de l'utilisateur ${RUN_USER}"
  useradd --system --create-home --shell /usr/sbin/nologin "${RUN_USER}"
fi

mkdir -p "${BASE}"

# The tree belongs to ${RUN_USER} but this script runs as root, and git
# refuses to work on a repository owned by someone else unless told to. Scoped
# to this path rather than set globally: a blanket exception would cover every
# repository on the machine.
GIT=(git -c "safe.directory=${TARGET}")

if [[ -d "${TARGET}/.git" ]]; then
  echo "== mise à jour du dépôt"
  "${GIT[@]}" -C "${TARGET}" fetch --quiet origin
  "${GIT[@]}" -C "${TARGET}" reset --hard --quiet origin/main
else
  echo "== premier clonage"
  git clone --quiet "${REPO}" "${TARGET}"
fi

echo "== environnement Python"
if [[ ! -d "${TARGET}/.venv" ]]; then
  python3 -m venv "${TARGET}/.venv"
fi
"${TARGET}/.venv/bin/pip" install --quiet --upgrade pip
"${TARGET}/.venv/bin/pip" install --quiet -r "${TARGET}/requirements.txt"

# The setup cards live here and must outlive every redeploy.
mkdir -p "${TARGET}/data"

if [[ ! -f "${TARGET}/.env" ]]; then
  cp "${TARGET}/.env.example" "${TARGET}/.env"
  chmod 600 "${TARGET}/.env"
  echo
  echo "⚠️  ${TARGET}/.env vient d'être créé depuis l'exemple."
  echo "    Mettez-y DISCORD_TOKEN, puis relancez ce script."
  echo
fi
chmod 600 "${TARGET}/.env"
chown -R "${RUN_USER}:${RUN_USER}" "${TARGET}"

echo "== service systemd"
install -m 644 "${TARGET}/deploiement/${SERVICE}" "/etc/systemd/system/${SERVICE}"
systemctl daemon-reload
systemctl enable --quiet "${SERVICE}"

if grep -qE '^DISCORD_TOKEN=.+' "${TARGET}/.env"; then
  systemctl restart "${SERVICE}"
  sleep 3
  systemctl --no-pager --lines=15 status "${SERVICE}" || true
else
  echo "Service installé mais NON démarré : DISCORD_TOKEN est vide dans ${TARGET}/.env"
fi
