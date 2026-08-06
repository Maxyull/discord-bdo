# Déploiement sur le VPS

## Où ça vit

```
/opt/discordbot/
  discord-bdo/      ← ce bot
  <autre-bot>/      ← les suivants, même modèle
```

Un dossier par bot sous `/opt/discordbot/`, un service systemd par bot, et un
seul compte système `discordbot` non privilégié pour tous.

⚠️ **`rubin-bot` n'est pas là.** Il tourne depuis `/opt/rubin-bot`, en service
systemd `rubin-bot.service`, et il est **en ligne**. Le déplacer sous
`/opt/discordbot/` couperait le service : à faire un jour, à froid, pas au
passage.

## Pourquoi systemd et pas Docker

Le dépôt contient un `Dockerfile` et un `docker-compose.yml` qui marchent, mais
le VPS fait déjà tourner ses bots en systemd (`rubin-bot.service`,
`rubin.service`). Deux mécanismes pour la même chose sur la même machine, c'est
une chose de plus à savoir le jour où quelque chose casse à 2 h du matin.

Docker reste utile pour tourner ailleurs, ou en local.

## Installer

```bash
sudo bash deploiement/installer.sh
```

Le script est **idempotent** : relancez-le pour déployer une nouvelle version.
Il crée le compte système au besoin, clone ou met à jour le dépôt, construit
l'environnement Python, installe le service, et redémarre.

Il ne touche **jamais** au `.env` existant : le jeton survit à chaque mise à
jour. Au premier passage il le crée depuis `.env.example` et s'arrête là, en
vous disant de le remplir.

## Le jeton

```bash
sudo -u discordbot nano /opt/discordbot/discord-bdo/.env
```

Renseignez `DISCORD_TOKEN`, puis relancez le script d'installation.

Le fichier est en `600`, lisible du seul compte `discordbot`. Il n'est pas dans
le dépôt et ne doit jamais y entrer : **le dépôt est public**.

## Exploitation

```bash
sudo systemctl status discord-bdo      # état
sudo journalctl -u discord-bdo -f      # journal en direct
sudo systemctl restart discord-bdo     # redémarrage
```

Le service redémarre tout seul en cas de coupure : Discord ferme régulièrement
les connexions longues, et un bot qui ne revient pas est un bot mort avec des
boutons qui ne répondent plus.

## Les données

Une seule chose à sauvegarder : `data/profiles.db`, les fiches de
configuration. Le script de déploiement ne l'efface pas, mais un `rm -rf` du
dossier, si.

```bash
sudo cp /opt/discordbot/discord-bdo/data/profiles.db ~/sauvegarde-profiles.db
```

## Durcissement

Le service tourne sous un compte dédié, sans droits d'élévation, avec
`ProtectSystem=strict` : le seul chemin ouvert en écriture est son propre
dossier `data/`. Il n'écoute aucun port, il ne fait que des connexions
sortantes vers Discord et GitHub.
