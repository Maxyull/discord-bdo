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
📢 Infos            bienvenue-welcome · règles-rules · annonces-announcements · état-status · guides-tutoriels (forum)
💬 Communauté       chat-fr · captures-screenshots
🪙 Butin            butin-aide-help · butin-bugs (forum) · butin-suggestions (forum) · butin-versions-releases
⏱️ Rubin            rubin-aide-help · rubin-bugs (forum) · rubin-suggestions (forum) · rubin-versions-releases
🧪 Bêta   (privé)   beta-annonces-news · beta-chat · beta-retours-feedback (forum)
🔒 Staff  (privé)   staff-configs · staff-journal
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

**Un seul salon de discussion**, pas un par langue : à deux membres, deux salons font
paraître le serveur deux fois plus vide. Le français et l'anglais y sont acceptés, et le
sujet du salon le dit, pour que son nom ne dissuade pas un anglophone.

Ni vocal, ni salon d'équipe : ils n'auraient servi à personne. Ils se rajoutent en une
ligne dans `src/blueprint.py` le jour où le serveur les mérite.

Les salons de bugs et de suggestions sont des **forums**, avec des étiquettes de suivi
(`Nouveau`, `Confirmé`, `Corrigé`, `Rejeté`). Un sujet = un fil, donc rien ne se perd
dans le défilement.

### Le tableau d'état

`#état-status` est un salon verrouillé où le bot tient à jour **un seul message**, vert,
jaune ou rouge par service. Il est vérifié tout seul **toutes les 5 minutes**.

| Sonde | Ce qui est vérifié | Ce que le rouge veut dire |
| --- | --- | --- |
| **API Rubin** | `rubin.maxyull.fr/sante` répond `etat: ok` | Rubin ne peut plus envoyer ses temps |
| **Téléchargement Butin** | la dernière version est servie par GitHub | personne ne peut installer Butin |
| **Téléchargement Rubin** | idem | personne ne peut installer Rubin |
| **BDOCodex** | le référentiel des noms d'objets et de quêtes | les noms ne se mettent plus à jour |
| **Veliainn** | la source des prix de Butin | les prix peuvent dater |
| **maxyull.fr** | le site | — |

Les six sondes partent **en parallèle**, l'ensemble prend moins d'une seconde. Une sonde
lente ne retarde pas les autres.

Le jaune n'est pas un rouge poli, il a un sens précis : le service **a répondu**, mais
lentement, avec un code inattendu, ou en se déclarant lui-même en mauvais état. C'est le
cas de l'API Rubin, dont la sonde lit le corps de la réponse et pas seulement le code :
un service qui renvoie `200` en annonçant `etat: degraded` est jaune, pas vert.

Quand quelque chose ne va pas, le message **dit ce qui casse pour l'utilisateur**, pas
seulement quel serveur est tombé :

```
🔴 API Rubin — pas de réponse / timeout
🟡 Référentiel BDOCodex  4200 ms — lent / slow

> Rubin ne peut plus envoyer ses temps / Rubin cannot sync your runs
> Les noms d'objets et de quêtes ne se mettent plus à jour
```

**Le message n'est réécrit que si un état change.** L'horodatage est un `<t:…:R>`, que
Discord transforme en « il y a 3 minutes » côté lecteur et met à jour tout seul : un
tableau tout vert n'a donc besoin d'aucune écriture. Une réécriture de sécurité a lieu au
maximum toutes les 30 minutes, pour prouver que la surveillance tourne encore.

Chaque bascule d'un service part dans `#staff-journal`, une ligne par transition. Vous
voyez donc l'historique sans polluer le salon public.

`/etat` relance les sondes à la demande et répond en privé.

Une panne de la surveillance ne peut pas emporter le bot : la boucle attrape tout, et une
sonde en échec est un résultat rouge, pas une exception.

### Les guides

`#guides-tutoriels` est un forum, pas un salon texte : un guide d'installation noyé sous
trois mois de messages n'est plus un guide. Un fil par sujet, filtrable par étiquette :

`🪙 Butin` · `⏱️ Rubin` · `Installation` · `Calibrage / Setup` · `Astuce / Tip` · `Dépannage`

Un seul forum pour les deux logiciels, avec les étiquettes qui font le tri, plutôt que
deux salons à moitié vides. Les étiquettes produit sont en premier parce que c'est le
filtre qu'on cherche en arrivant.

**Seule l'équipe ouvre un fil**, mais tout le monde peut répondre dedans : une question
posée sous le guide qu'elle concerne reste au bon endroit. C'est la raison pour laquelle
le niveau « lecture seule » autorise les réponses en fil tout en interdisant d'ouvrir un
sujet.

**Six guides sont publiés automatiquement** par le script, écrits à partir des README des
deux projets :

| Guide | Étiquettes |
| --- | --- |
| Installer Butin | Butin · Installation |
| Premier lancement et calibrage | Butin · Calibrage |
| Où sont mes sessions | Butin · Astuce |
| Butin ne compte rien, que faire | Butin · Dépannage |
| Installer Rubin | Rubin · Installation |
| Est-ce autorisé, et que sort-il de mon PC | Butin · Rubin · Astuce |

Ils sont posés **une fois**. Un guide déjà présent n'est ni recréé ni réécrit, y compris
s'il a été archivé par Discord faute de lecture : vous pouvez donc les corriger à la main
sur Discord sans qu'un `/setup` n'écrase votre travail.

Leur contenu vient des README de `butin-bdo` et `rubin-bdo`, pas d'une reconstitution.
Quand les logiciels changent, `src/guides.py` change avec eux.

Le script **ne supprime jamais rien**. Relancé, il ne recrée que ce qui manque.

---

## Mise en route

### 1. Le serveur existe déjà, ne pas en créer un autre

> ⚠️ **`BDO Tools Rubin Loot Tracker`**, identifiant **`1534377319945469972`**.
>
> Son lien d'invitation `discord.gg/qCuvN2Zna7` est **déjà publié dans les README publics
> de `butin-bdo` et de `rubin-bdo`**. Les utilisateurs y arrivent donc dès maintenant.
> Construire un second serveur laisserait ce lien pointer vers un serveur vide.

C'est ce serveur-là qu'il faut passer au script. Son salon `general` existant ne sera pas
touché : le script ne supprime jamais rien, il ajoute ce qui manque.

Il n'a pas encore le mode Communauté, le script l'activera lui-même (voir l'étape 5).

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

Remplissez `DISCORD_TOKEN`. `DISCORD_GUILD_ID` est déjà renseigné dans `.env.example`
avec l'identifiant du serveur existant, ne le changez pas sans raison.

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
d'accueil bêta, pose dans chaque salon d'aide les deux panneaux (rapport et
configuration), et **publie les six guides de départ** dans le forum. Il affiche à la fin
ce qu'il a fait.

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

> ⚠️ **Un autre bot est déjà sur ce serveur.** `rubin-bot`, le robot de consultation du
> classement Rubin, tourne sur le VPS depuis `/opt/rubin-bot` et est connecté en
> permanence. Il expose `/rapides`, `/chaine` et `/quete` ; aucune commande d'ici ne
> porte ces noms, et un test le vérifie. Les deux bots sont complémentaires : celui-ci
> gère le serveur, l'autre répond sur les temps de quête.

### Sur le VPS

Voir [`deploiement/LISEZ-MOI.md`](deploiement/LISEZ-MOI.md). En résumé :

```bash
sudo bash deploiement/installer.sh
```

Un dossier par bot sous `/opt/discordbot/`, un service systemd chacun, un seul compte
système non privilégié. Le script est idempotent et ne touche jamais au `.env`, donc le
jeton survit aux mises à jour.

**systemd plutôt que Docker** : le `Dockerfile` fonctionne, mais le VPS fait déjà tourner
ses bots en systemd. Deux mécanismes pour la même chose sur la même machine, c'est une
chose de plus à savoir le jour où ça casse.

### Ailleurs


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
| `/version` | Tout le monde | Dernières versions publiées, lues en direct sur GitHub |
| `/etat` | Tout le monde | Relance les sondes et affiche l'état en direct |
| `/tester @membre` | Staff | Donne le rôle `Tester`, `retirer:true` pour l'enlever |
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

350 tests, sans réseau ni jeton. Ils couvrent le plan du serveur (clés en double, noms
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
