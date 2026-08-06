# discord-bdo

Le serveur Discord de **Butin** (suivi de butin) et **Rubin** (chronomètre de quêtes),
construit par un script plutôt qu'à la main.

Quatre choses vivent ici :

1. **Un plan de serveur** (`src/blueprint.py`) : catégories, salons, rôles, permissions.
   Un script le pose sur un serveur vide en une commande, et le répare si quelque chose
   a été supprimé par erreur.
2. **Un bot** : deux boutons par logiciel, *Signaler un bug* et *Proposer une idée*.
   Ils ouvrent un formulaire, créent un fil au bon endroit, et **ouvrent l'issue GitHub**
   correspondante dans `butin-bdo` ou `rubin-bdo`, avec un lien croisé dans les deux sens.
3. **Un pont de versions** : chaque publication GitHub s'annonce toute seule dans le salon
   de versions du logiciel concerné. Ça, c'est un simple webhook, aucun serveur à faire tourner.
4. **Une fiche de configuration** : écran, échelle Windows, échelle de l'interface du jeu,
   mode d'affichage, machine. Remplie une fois par n'importe quel membre, elle est ensuite
   jointe automatiquement à tous ses rapports de bug, avec la gestion des captures qui va
   avec. Plus une catégorie bêta privée, réservée au rôle `Tester`.

---

## Ce que le script construit

```
📢 Infos            bienvenue-welcome · règles-rules · annonces-announcements
💬 Communauté       chat-fr · chat-en · captures-screenshots · Vocal
🪙 Butin            butin-aide-help · butin-bugs (forum) · butin-suggestions (forum) · butin-versions-releases
⏱️ Rubin            rubin-aide-help · rubin-bugs (forum) · rubin-suggestions (forum) · rubin-versions-releases
🧪 Bêta   (privé)   beta-annonces-news · beta-chat · beta-retours-feedback (forum)
🔒 Staff  (privé)   staff-chat · staff-configs · staff-journal
```

Rôles créés, du haut vers le bas : `Dev`, `Mod`, `Tester`, `Joueur`, `Muted`.

| Rôle | Ce qu'il donne |
| --- | --- |
| `Dev` | Administrateur. Le vôtre. |
| `Mod` | Gérer messages et fils, exclure, rendre muet. Pas bannir. |
| `Tester` | **La catégorie 🧪 Bêta**, invisible pour tous les autres. Donné à la main. La fiche de config, elle, est ouverte à tous. |
| `Joueur` | Posé automatiquement à l'arrivée. Sert à mentionner les humains sans `@everyone`. |
| `Muted` | Retire écriture, fils et réactions sur **tous** les salons du plan. |

L'ordre compte : Discord décide qui peut modérer qui par la position dans la liste, pas
par le nom de la permission. Le script impose donc l'ordre après création. Un `Mod` placé
sous `Joueur` ne peut mettre personne en timeout.

Les salons **FR et EN sont visibles par tout le monde**, sans rôle à choisir : personne
n'est bloqué derrière un bouton de langue, et un anglophone voit tout de suite qu'il est
au bon endroit.

Les salons de bugs et de suggestions sont des **forums**, avec des étiquettes de suivi
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
3. Toujours dans **Bot**, activez **Server Members Intent** *et* **Message Content Intent**.
   Le premier sert à poser le rôle `Joueur` à l'arrivée, le second à voir les captures
   d'écran jointes : sans lui Discord vide la liste des pièces jointes et la détection
   ne se déclenche jamais, sans le moindre message d'erreur.
4. Onglet **OAuth2** → copiez le *Client ID*.

### 3. Inviter le bot

Ouvrez cette adresse en remplaçant `VOTRE_CLIENT_ID` :

```
https://discord.com/api/oauth2/authorize?client_id=VOTRE_CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

`permissions=8` est le droit Administrateur. Il est nécessaire pour créer les salons et
poser les permissions. Une fois le serveur construit, vous pouvez le réduire, voyez
*Réduire les droits du bot* plus bas.

Dans *Paramètres du serveur → Rôles*, **remontez le rôle du bot tout en haut**, au-dessus
de `Dev`. Discord interdit à un bot de gérer un rôle placé plus haut que le sien : sans
ça le setup échoue à mi-parcours, et l'ordre des rôles ne peut pas être appliqué.

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

Le script crée les rôles et les met dans l'ordre, active le mode Communauté (obligatoire
pour les forums), crée les salons, écrit les messages de bienvenue, de règlement et
d'accueil bêta, et pose dans chaque salon d'aide les deux panneaux (rapport et
configuration). Il affiche à la fin ce qu'il a fait.

> **Si le mode Communauté ne s'active pas tout seul** (Discord le refuse parfois selon
> l'état du serveur), le script vous le dit et crée les forums en salons texte. Activez-le
> à la main dans *Paramètres du serveur → Activer la communauté*, supprimez les salons de
> bugs, de suggestions et de retours bêta, puis relancez `--setup` : ils reviendront en
> forums.

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
| `/config` | Tout le monde | Affiche sa fiche de configuration |
| `/config @membre` | Staff | Affiche la fiche de quelqu'un d'autre |
| `/aide` | Tout le monde | Rappelle où sont les boutons de rapport |

Un membre clique sur *Signaler un bug*, remplit quatre champs (résumé, version, système,
étapes), et il obtient :

- un fil dans `#butin-bugs` ou `#rubin-bugs`, étiqueté `Nouveau`, avec sa version, son
  système **et sa fiche de configuration si elle existe** ;
- une demande de capture d'écran postée dans le fil ;
- une issue GitHub étiquetée `bug` + `discord`, qui pointe vers le fil, avec la
  configuration en tableau ;
- une trace dans `#staff-journal`.

Quand la personne n'a pas de fiche, le rapport le dit explicitement plutôt que de laisser
un blanc : un vide se lit comme « configuration banale », ce qui est la mauvaise
conclusion à mettre sous les yeux de celui qui corrigera.

Si GitHub tombe ou si le jeton expire, **le fil Discord est créé quand même** et l'échec
est écrit dans `#staff-journal`. Un rapport d'utilisateur n'est jamais perdu à cause
d'une panne d'un service tiers.

---

## La fiche de configuration

Butin et Rubin **lisent l'écran**. Le même exécutable ne se comporte pas pareil en
1920x1080 à 100 % et en 2560x1440 à 150 %, ni en plein écran et en fenêtré sans bordure.
Sans ces informations, un rapport de bug d'OCR est une devinette.

D'où la **fiche de configuration**. Elle n'est **pas réservée aux testeurs** : le panneau
est posé dans les deux salons d'aide, à côté des boutons de rapport, parce que c'est
justement au moment de signaler un bug qu'elle sert.

Deux formulaires plutôt qu'un, parce que Discord plafonne un formulaire à cinq champs et
que ces cinq-là doivent aller à l'écran :

**🖥️ Mon écran et mon jeu** — ce qui décide du comportement de l'OCR

| Champ | Pourquoi il est là |
| --- | --- |
| Résolution écran | Détermine la taille des zones à calibrer |
| Échelle Windows | La cause la plus fréquente de calibrage faux, et celle à laquelle personne ne pense |
| **Échelle de l'interface (jeu)** | Réglage propre à Black Desert, **indépendant de celui de Windows**. Il change directement la taille du texte à lire |
| Affichage du jeu | Plein écran, fenêtré sans bordure et fenêtré ne capturent pas pareil |
| Langue du jeu | Décide quel dictionnaire OCR s'applique |

**⚙️ Ma machine** — processeur, carte graphique, mémoire. Facultatif : ça explique une
lenteur ou des images manquées, pas une lecture fausse.

Les deux moitiés s'enregistrent **séparément**. Remplir « Ma machine » n'efface pas ce qui
a été saisi dans « Mon écran » la semaine d'avant, et inversement. Ça a l'air évident, ça
ne l'était pas : la première version écrasait tout, et c'est un essai qui l'a montré.

La fiche est remplie **une fois**, stockée en SQLite, et **rejointe automatiquement à
tous les rapports de bug suivants** de cette personne, côté Discord comme côté issue
GitHub. Le rapporteur ne redonne jamais ces informations, et vous ne les redemandez jamais.

Les formulaires sont pré-remplis à la réouverture : corriger une valeur ne demande pas de
retaper les autres. Chaque fiche est miroitée dans `#staff-configs`, un message par membre,
mis à jour en place plutôt qu'empilé : le salon reste un annuaire, et il est **côté staff**
parce que ce sont des informations matérielles sur des personnes réelles.

Résolutions et pourcentages sont normalisés à l'entrée : `2560 * 1440`, `2560×1440` et
`2560 par 1440` donnent tous `2560x1440` ; `1.5`, `150` et `150 %` donnent `150%`.
Un texte libre qui ne ressemble pas à une valeur est **laissé tel quel** plutôt que
transformé, parce qu'une valeur inventée est pire que les mots de l'utilisateur.

`/config` affiche sa propre fiche. `/config @membre` est réservé au staff.

### Les captures d'écran

Discord **n'accepte aucun fichier dans un formulaire**, c'est une limite de la plateforme,
pas un choix. Le flux contourne le problème :

1. le rapport crée le fil ;
2. le bot y poste immédiatement la marche à suivre, avec la consigne qui compte pour
   Butin : cadrer **la fenêtre du jeu entière**, pas seulement le compteur, puisque le
   calibrage dépend de ce qu'il y a autour ;
3. dès qu'une image ou une vidéo arrive dans le fil, le bot la marque d'un 📎, pose
   l'étiquette `Capture / Screenshot` sur le fil et prévient `#staff-journal`.

Vous filtrez donc le forum sur cette étiquette pour voir d'un coup d'œil quels bugs sont
exploitables. Le remerciement part **une fois par fil**, pas une fois par image.

Cette détection a un coût : elle exige l'intent privilégié *Message Content*, sans lequel
Discord vide `message.attachments` et la détection ne se déclencherait jamais, en silence.
Il s'active en un clic tant que le bot est sur moins de 100 serveurs.

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

## Les données stockées

Une seule base, `data/profiles.db`, une seule table : les fiches de configuration, une
par membre (résolution, échelle Windows, échelle de l'interface du jeu, mode d'affichage,
langue du jeu, processeur, carte graphique, mémoire). Rien d'autre n'est conservé, ni les messages, ni les rapports, ni l'historique.

Sur le VPS elle vit dans un volume Docker nommé, donc un `docker compose up --build` ne
l'efface pas. Ce sont des informations matérielles sur des personnes réelles : la
consultation croisée est réservée au staff, et une fiche se supprime sur demande.

---

## Tests

```bash
.venv\Scripts\python.exe -m pytest -q
```

229 tests, sans réseau ni jeton. Ils couvrent le plan du serveur (clés en double, noms
qui se télescopent une fois normalisés par Discord, limites de caractères des formulaires
et des étiquettes), les tables de permissions y compris l'étanchéité de la catégorie
bêta, le stockage des fiches, la normalisation des résolutions et des échelles, la
reconnaissance des pièces jointes, le pont GitHub avec ses pannes, et le découpage des
textes trop longs.

Ils ne sont pas décoratifs, ils ont déjà attrapé trois erreurs qui auraient cassé le
produit en vrai :

- deux libellés de formulaire à 48 et 49 caractères, au-dessus de la limite de 45, qui
  auraient fait rejeter le formulaire de suggestion à l'ouverture ;
- un texte d'exemple à 110 caractères, au-dessus de la limite de 100, même conséquence
  sur le formulaire de bug ;
- une sauvegarde qui écrasait la moitié de la fiche : remplir « Ma machine » remettait à
  zéro la résolution et les échelles saisies plus tôt.

---

## Installation depuis zéro

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Python 3.10 ou plus. `requirements.txt` seul suffit en production.
