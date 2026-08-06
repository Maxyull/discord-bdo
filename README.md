# discord-bdo

Le serveur Discord de **Butin** (suivi de butin) et **Rubin** (chronomètre de quêtes),
construit par un script plutôt qu'à la main.

Trois choses vivent ici :

1. **Un plan de serveur** (`src/blueprint.py`) : catégories, salons, rôles, permissions.
   Un script le pose sur un serveur vide en une commande, et le répare si quelque chose
   a été supprimé par erreur.
2. **Un bot** : deux boutons par logiciel, *Signaler un bug* et *Proposer une idée*.
   Ils ouvrent un formulaire, créent un fil au bon endroit, et **ouvrent l'issue GitHub**
   correspondante dans `butin-bdo` ou `rubin-bdo`, avec un lien croisé dans les deux sens.
3. **Un pont de versions** : chaque publication GitHub s'annonce toute seule dans le salon
   de versions du logiciel concerné. Ça, c'est un simple webhook, aucun serveur à faire tourner.

---

## Ce que le script construit

```
📢 Infos            bienvenue-welcome · règles-rules · annonces-announcements
💬 Communauté       chat-fr · chat-en · captures-screenshots · Vocal
🪙 Butin            butin-aide-help · butin-bugs (forum) · butin-idées-ideas (forum) · butin-versions-releases
⏱️ Rubin            rubin-aide-help · rubin-bugs (forum) · rubin-idées-ideas (forum) · rubin-versions-releases
🔒 Staff            staff-chat · staff-journal
```

Rôles créés : `Staff`, `Moderator`, `Tester`, `Muted`.

Les salons **FR et EN sont visibles par tout le monde**, sans rôle à choisir : personne
n'est bloqué derrière un bouton de langue, et un anglophone voit tout de suite qu'il est
au bon endroit.

Les salons de bugs et d'idées sont des **forums**, avec des étiquettes de suivi
(`Nouveau`, `Confirmé`, `Corrigé`, `Rejeté`). Un sujet = un fil, donc rien ne se perd
dans le défilement.

Le script **ne supprime jamais rien**. Relancé, il ne recrée que ce qui manque.

---

## Mise en route

### 1. Créer le serveur

Dans Discord, `+` en bas de la liste des serveurs → *Créer le mien* → *À usage personnel*.
Nom au choix, par exemple `Butin & Rubin`. Laissez-le vide, le script s'occupe du reste.

Activez ensuite le mode développeur : *Paramètres utilisateur → Avancés → Mode développeur*.
Clic droit sur l'icône du serveur → *Copier l'identifiant du serveur*. Gardez-le sous la main.

### 2. Créer le bot

Sur https://discord.com/developers/applications :

1. *New Application*, nommez-la `Butin & Rubin`.
2. Onglet **Bot** → *Reset Token* → copiez le jeton. **Il ne s'affiche qu'une fois.**
3. Toujours dans **Bot**, activez **Server Members Intent**.
   (Message Content Intent n'est pas nécessaire, laissez-le éteint.)
4. Onglet **OAuth2** → copiez le *Client ID*.

### 3. Inviter le bot

Ouvrez cette adresse en remplaçant `VOTRE_CLIENT_ID` :

```
https://discord.com/api/oauth2/authorize?client_id=VOTRE_CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

`permissions=8` est le droit Administrateur. Il est nécessaire pour créer les salons et
poser les permissions. Une fois le serveur construit, vous pouvez le réduire, voyez
*Réduire les droits du bot* plus bas.

Dans *Paramètres du serveur → Rôles*, **remontez le rôle du bot au-dessus de `Staff`**.
Discord interdit à un bot de gérer un rôle placé plus haut que le sien, et le setup
échouerait à mi-parcours.

### 4. Configurer

```bash
copy .env.example .env
```

Remplissez `DISCORD_TOKEN` et `DISCORD_GUILD_ID`.

`GITHUB_TOKEN` est facultatif : sans lui tout fonctionne, il manque seulement la création
automatique d'issues. Pour l'activer, créez un jeton sur
https://github.com/settings/tokens avec la portée `repo` (classique), ou un jeton
*fine-grained* limité à `butin-bdo` et `rubin-bdo` avec **Issues: Read and write**.

### 5. Construire le serveur

Vérifiez d'abord le plan, hors ligne, sans rien toucher :

```bash
.venv\Scripts\python.exe main.py --check
```

Puis construisez pour de vrai :

```bash
.venv\Scripts\python.exe main.py --setup
```

Le script crée les rôles, active le mode Communauté (obligatoire pour les forums),
crée les salons, écrit les messages de bienvenue et de règlement, et pose les panneaux
de boutons dans les deux salons d'aide. Il affiche à la fin ce qu'il a fait.

> **Si le mode Communauté ne s'active pas tout seul** (Discord le refuse parfois selon
> l'état du serveur), le script vous le dit et crée les forums en salons texte. Activez-le
> à la main dans *Paramètres du serveur → Activer la communauté*, supprimez les quatre
> salons de bugs/idées, puis relancez `--setup` : ils reviendront en forums.

### 6. Brancher les annonces de version

Dans Discord, sur `#butin-versions-releases` : *Modifier le salon → Intégrations →
Webhooks → Nouveau webhook → Copier l'URL du webhook*. Pareil pour `#rubin-versions-releases`.

```bash
set GITHUB_TOKEN=ghp_votre_jeton
.venv\Scripts\python.exe scripts\link_releases.py --butin URL_BUTIN --rubin URL_RUBIN
```

Le script s'abonne **aux publications uniquement**. Il ne s'abonne pas aux commits :
un salon d'annonces qui reçoit chaque push devient illisible en une journée.
Relancé deux fois, il détecte le webhook existant et ne fait rien.

---

## Faire tourner le bot

En local, pour essayer :

```bash
.venv\Scripts\python.exe main.py
```

Sur le VPS, à côté des autres services :

```bash
docker compose up -d --build
docker compose logs -f
```

Le conteneur n'ouvre aucun port, il ne fait que des connexions sortantes.
Il tourne sous un utilisateur non privilégié.

**Le bot doit tourner en permanence pour que les boutons répondent.** S'il est hors ligne,
Discord affiche « L'interaction a échoué » au clic. Les fils déjà créés, eux, restent là.

---

## Utilisation au quotidien

| Commande | Qui | Effet |
| --- | --- | --- |
| `/setup` | Staff | Reconstruit ou répare le serveur, sans rien supprimer |
| `/aide` | Tout le monde | Rappelle où sont les boutons de rapport |

Un membre clique sur *Signaler un bug*, remplit quatre champs (résumé, version, système,
étapes), et il obtient :

- un fil dans `#butin-bugs` ou `#rubin-bugs`, étiqueté `Nouveau`, avec sa version et son système ;
- une issue GitHub étiquetée `bug` + `discord`, qui pointe vers le fil ;
- une trace dans `#staff-journal`.

Si GitHub tombe ou si le jeton expire, **le fil Discord est créé quand même** et l'échec
est écrit dans `#staff-journal`. Un rapport d'utilisateur n'est jamais perdu à cause
d'une panne d'un service tiers.

---

## Modifier le serveur plus tard

Tout est dans `src/blueprint.py`. Ajouter un salon, c'est une ligne :

```python
ChannelSpec(name="mon-salon", topic="À quoi il sert"),
```

Puis `main.py --check` pour valider, `/setup` dans Discord pour appliquer.

Les textes affichés aux membres sont tous dans `src/texts.py`, séparés de la logique :
corriger une faute ne demande pas de lire une ligne de code.

**Un salon retiré du plan n'est pas supprimé sur Discord.** C'est délibéré : une
suppression automatique d'un salon plein de rapports n'est pas une erreur dont on revient.
Supprimez-le à la main si c'est vraiment voulu.

---

## Réduire les droits du bot

Une fois le serveur construit, l'Administrateur n'est plus nécessaire pour l'usage
courant. Le bot a besoin de : *Gérer les salons*, *Gérer les rôles*, *Voir les salons*,
*Envoyer des messages*, *Créer des fils publics*, *Envoyer des messages dans les fils*,
*Intégrer des liens*, *Gérer les messages*.

Gardez l'Administrateur si vous comptez relancer `/setup` de temps en temps, c'est plus
simple que de deviner quel droit manque.

---

## Tests

```bash
.venv\Scripts\python.exe -m pytest -q
```

112 tests, sans réseau ni jeton. Ils couvrent le plan du serveur (clés en double, noms
qui se télescopent une fois normalisés par Discord, limites de caractères des formulaires
et des étiquettes), les tables de permissions, le pont GitHub avec ses pannes, et le
découpage des textes trop longs.

Ils ne sont pas décoratifs : ils ont attrapé deux libellés de formulaire à 48 et 49
caractères, au-dessus de la limite de 45 de Discord, qui auraient fait rejeter le
formulaire de suggestion à l'ouverture.

---

## Installation depuis zéro

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Python 3.10 ou plus. `requirements.txt` seul suffit en production.
