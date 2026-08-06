# Les visuels du serveur

Six fichiers, faits le 06/08/2026. Le jeu complet des deux logiciels vit à
côté, dans `D:\DEV\bdo\ressources\`, et se régénère avec
`python D:/DEV/bdo/logos/kit/build_kit.py`.

Le style commun aux deux logiciels et au serveur : polygone facetté au trait,
sur fond `#15171C`. Or `#D4A955` pour Butin, rouge `#CF2B45` pour Rubin,
violet pour le bot, et l'écu mi-or mi-rouge pour le serveur, qui les réunit.

| Fichier | Où il va | Taille |
|---|---|---|
| `discord-serveur.png` | icône du serveur | 512 |
| `bot-avatar.png` | avatar du bot | 512 |
| `embed-butin.png` | vignette des embeds qui parlent de Butin | 256 |
| `embed-rubin.png` | vignette des embeds qui parlent de Rubin | 256 |
| `couverture-discord.png` | bannière du serveur, en-tête d'invitation | 1920 × 480 |
| `pub-discord-1-1.png` | post carré prêt à partager, lien inclus | 1080 × 1080 |

## Ce que le dépôt n'en fait pas encore

⚠️ **Aucun de ces fichiers n'est lu par le code.** Ils sont ici comme source,
pas comme dépendance. Rien ne casse si on les déplace.

Deux branchements possibles, ni faits ni décidés :

1. **L'icône du serveur et l'avatar du bot se posent à la main**, dans
   l'interface Discord. `setup_guild.py` pourrait les poser lui-même
   (`guild.edit(icon=...)`), ce qui rendrait la reconstruction d'un serveur
   vide complète au lieu de s'arrêter à la structure. Ça demande de vérifier
   le comportement contre un vrai serveur, ce qui n'a pas été fait.
2. **Les embeds n'ont pas de vignette.** Les y ajouter suppose de trancher
   comment Discord reçoit l'image : fichier joint à chaque envoi, ou URL
   hébergée une fois pour toutes. Les deux ont des inconvénients différents,
   et personne n'a arbitré.
