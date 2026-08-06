"""Starter content for the guide forum.

Every line here comes from the two projects' own READMEs and docs, not from
guesswork: a wrong install instruction costs more than a missing one. When the
tools change, these change with them.

The setup pass posts one thread per guide and skips any title that already
exists, so it can be re-run without duplicating anything and without
overwriting an edit made by hand on Discord.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import blueprint as bp

#: Discord caps a message at 2000 characters, so guides stay short and point
#: at the README for the long version.
BODY_LIMIT = 2000

TAG_BUTIN = bp.GUIDE_TAGS[0]
TAG_RUBIN = bp.GUIDE_TAGS[1]
TAG_INSTALL = bp.GUIDE_TAGS[2]
TAG_SETUP = bp.GUIDE_TAGS[3]
TAG_TIP = bp.GUIDE_TAGS[4]
TAG_TROUBLE = bp.GUIDE_TAGS[5]

BUTIN_REPO = "https://github.com/Maxyull/butin-bdo"
RUBIN_REPO = "https://github.com/Maxyull/rubin-bdo"


@dataclass(frozen=True)
class Guide:
    title: str
    tags: tuple[str, ...]
    body: str


GUIDES: tuple[Guide, ...] = (
    Guide(
        title="🪙 Installer Butin",
        tags=(TAG_BUTIN, TAG_INSTALL),
        body=f"""\
**Butin, c'est quoi** : le suivi de butin pour Black Desert, sur PC Windows. Il lit le journal d'acquisition pendant que vous farmez et vous dit ce que la session a rapporté, en silver par heure.

**Le plus simple**
Téléchargez l'installeur Windows sur la page des versions :
{BUTIN_REPO}/releases/latest

Il ne demande **aucun droit administrateur**. Une fois installé, lancez **`butin-app`** : une fenêtre s'ouvre, tout se fait dedans. Pas de terminal, pas de navigateur, pas d'adresse à taper.

**Depuis les sources**, si vous préférez :
```
git clone {BUTIN_REPO}
cd butin-bdo
python -m venv .venv
.venv\\Scripts\\activate
pip install -e ".[dev]"
```
Rien d'autre à installer que Python : le moteur de reconnaissance de texte arrive avec, il n'y a pas de Tesseract à poser à la main ni de `PATH` à régler.

➡️ Ensuite, passez au calibrage, c'est l'étape qui décide si ça marche.

*Butin est en version 0.y.z : rien n'est encore promis stable d'une version à l'autre, y compris le format de la base de sessions.*
""",
    ),
    Guide(
        title="🪙 Premier lancement et calibrage",
        tags=(TAG_BUTIN, TAG_SETUP),
        body="""\
**C'est l'étape qui compte.** Butin lit des pixels : s'il ne sait pas où regarder, il ne compte rien.

**Dans l'ordre**
1. Lancez le jeu, et faites en sorte que le **journal d'acquisition soit visible** à l'écran.
2. Lancez `butin-app`, onglet **Réglages**.
3. Vérifiez le dossier des sessions, changez-le si celui par défaut ne vous va pas.
4. **Calibrer la zone**.
5. **Regardez ce que la fenêtre affiche** : elle montre les lignes qu'elle vient de lire. Ce doit être votre chat, avec vos lignes. Si ce n'est pas le cas, ne lancez pas de session, ça ne comptera rien de bon.

**Ensuite, pour farmer**
**Commencer le grind** vous laisse cinq secondes pour basculer dans le jeu, puis pose un **panneau translucide par-dessus** : silver par heure, total net, durée, et chaque drop au moment où il tombe, coloré selon sa rareté.

C'est le seul écran à regarder en farmant. La fenêtre principale reste derrière le jeu. Le bouton **Arrêter** du panneau ferme la session.

**Si le calibrage automatique se trompe**, dites-le dans le salon d'aide avec une capture de la **fenêtre du jeu entière**, pas seulement du chat : le calibrage dépend de ce qu'il y a autour.
""",
    ),
    Guide(
        title="🪙 Où sont mes sessions",
        tags=(TAG_BUTIN, TAG_TIP),
        body="""\
Dans **`Documents\\BDO Tracker`**, par défaut.

C'est volontaire : ce sont vos données, vous voudrez les sauvegarder ou les retrouver, pas les chercher dans un dossier caché de `%LOCALAPPDATA%`.

Le dossier est affiché dans les **Réglages** et se change.

⚠️ **Deux choses à savoir avant de le changer**
- le changement **ne déplace rien**, les anciennes sessions restent où elles sont ;
- il prend effet **au prochain lancement**, pas tout de suite. La base est ouverte à cet instant, et déplacer un fichier de base ouvert est le meilleur moyen de le perdre.

Pour sauvegarder vos sessions, copiez le dossier **quand Butin est fermé**.
""",
    ),
    Guide(
        title="🪙 Butin ne compte rien, que faire",
        tags=(TAG_BUTIN, TAG_TROUBLE),
        body="""\
Dans l'ordre, du plus fréquent au plus rare.

**1. Le journal d'acquisition n'est pas visible.** Butin lit l'écran. Si le journal est fermé, replié, ou masqué par une autre fenêtre, il n'y a rien à lire.

**2. Le calibrage ne vise pas le bon endroit.** Refaites *Réglages → Calibrer la zone*, et **lisez les lignes affichées** : si ce n'est pas votre chat, c'est le calibrage.

**3. Vous avez changé de résolution ou d'échelle depuis le calibrage.** La zone est mesurée en pixels. Changer la résolution de l'écran, l'échelle Windows ou l'échelle de l'interface du jeu invalide le calibrage. Refaites-le.

**4. Le compteur est un peu bas.** C'est assumé : partout où il y a un doute, Butin **ne compte pas**. Rater un drop donne un chiffre un peu bas, inventer un drop donne un chiffre faux, et un chiffre faux vous fait changer de spot pour de mauvaises raisons.

**Rien n'y fait ?** Utilisez le bouton **🐛 Signaler un bug** dans le salon d'aide de Butin. Remplissez d'abord votre fiche de configuration : sans la résolution et les deux échelles, un bug de lecture d'écran est indevinable.
""",
    ),
    Guide(
        title="⏱️ Installer Rubin",
        tags=(TAG_RUBIN, TAG_INSTALL),
        body=f"""\
**Rubin, c'est quoi** : le chronomètre de quêtes pour Black Desert, sur PC Windows. Il lit le bandeau de quête en bas à droite et mesure combien de temps vous mettez.

**Téléchargement**
{RUBIN_REPO}/releases/latest

**Comment il fonctionne**
Le jeu affiche un bandeau à chaque changement d'état de quête :
- `Nouvelle quête`, en jaune → départ du chronomètre
- `Quête accomplie`, en cyan → arrêt

Rubin surveille cette seule zone, environ 400 × 160 pixels, et ne réveille la lecture que quand les pixels bougent. Quelques dizaines de lectures par heure, pas des milliers.

**Ce n'est pas un minuteur, c'est un journal.** Quand on enchaîne vite, un bandeau d'accomplissement peut passer sans être vu. Rubin note ce qu'il voit et reconstruit les durées après coup, en indiquant leur qualité : exacte, déduite, ou écartée. Il préfère écarter une mesure plutôt que l'attribuer au hasard.

⚠️ **Le classement est encore presque vide** : quelques mesures, d'un seul joueur, sur une seule chaîne. Ce sont des mesures, pas encore des références. Ça se comble en jouant.
""",
    ),
    Guide(
        title="🪙 Le panneau posé sur le jeu",
        tags=(TAG_BUTIN, TAG_TIP),
        body="""\
Butin a **deux fenêtres**, et on ne regarde pas la même selon ce qu'on fait.

**La fenêtre principale**, avant et après la session. Deux onglets :
- **Réglages** : le dossier des sessions, le calibrage de la zone de chat, le taux de taxe, et le bouton qui lance le grind.
- **Historique** : vos sessions passées, avec durée, nombre d'objets, silver par heure et total net. Cliquez une ligne pour voir le détail du butin.

**Le panneau en surimpression**, pendant le farm. *Commencer le grind* vous laisse cinq secondes pour basculer dans le jeu, puis pose un panneau **translucide par-dessus** :
- silver par heure, total net, durée ;
- **chaque drop au moment où il tombe**, avec sa quantité, sa valeur et son nom **coloré selon sa rareté** dans le jeu.

Sans cadre, toujours au-dessus, déplaçable par sa barre de titre. C'est le seul écran à regarder en farmant, la fenêtre principale reste derrière le jeu.

**Bouton Arrêter** : ferme la session et le panneau avec elle.

**Pause** : le temps en pause est déduit de la durée, donc votre silver/heure ne s'effondre pas parce que vous êtes allé manger.

💡 Placez le panneau **loin de la zone de chat calibrée**. Butin lit une capture d'écran : une fenêtre posée sur la zone qu'il lit est lue à la place de cette zone, et la transparence n'y change rien puisque c'est le mélange des deux qui est capturé.
""",
    ),
    Guide(
        title="⏱️ Lire le classement Rubin",
        tags=(TAG_RUBIN, TAG_TIP),
        body="""\
Ouvrez la fenêtre de Rubin : quatre onglets.

**Session** — où vous en êtes et ce qui vient.
**Classement** — cherchez une quête par son nom, voyez les plus rapides.
**Zones** — les trois rectangles que Rubin lit **et ce qu'il y lit à l'instant**. C'est l'onglet qui répond en une seconde à « pourquoi ça ne mesure rien ».
**Réglages** — les curseurs, la langue du client, l'opacité.

**Comment le classement est calculé**
Par **quête**, pas par chaîne, et sur la **médiane** à partir de **trois mesures minimum**.

- Par quête, parce qu'une chaîne moyenne ses quêtes rapides et ses lentes, alors qu'on choisit quête par quête.
- Sur la médiane à partir de trois, parce qu'en dessous la première place irait toujours à une quête mesurée une seule fois par quelqu'un de chanceux.

Tant que rien n'atteint le seuil, la fenêtre **le dit** au lieu d'afficher un tableau vide.

**Pourquoi certaines de vos quêtes ne comptent pas**
Rubin est un journal d'événements, pas un minuteur. Quand vous enchaînez vite, un bandeau d'accomplissement peut passer sans être vu. Rubin note ce qu'il voit et reconstruit après coup, en indiquant la qualité : **exacte** (les deux bandeaux vus), **déduite** (par la chaîne), ou **écartée**. Une quête écartée vaut mieux qu'une durée attribuée au hasard.

⚠️ **Ne posez jamais la fenêtre sur une zone de lecture.** Elle se place d'elle-même à côté du panneau de quêtes et vous prévient si vous l'y déplacez.
""",
    ),
    Guide(
        title="⚖️ Est-ce autorisé, et que sort-il de mon PC",
        tags=(TAG_BUTIN, TAG_RUBIN, TAG_TIP),
        body="""\
**Les deux logiciels lisent des pixels à l'écran.** Rien d'autre.

Pas de lecture de la mémoire du jeu, pas d'injection, aucun fichier du client modifié, aucune action automatisée, aucune touche envoyée au jeu. C'est la même approche que les trackers utilisés par la communauté depuis des années, et c'est une **limite de conception**, pas une étape à franchir plus tard.

Cela dit, personne ne peut garantir à votre place la position de Pearl Abyss. Vous utilisez ces outils sous votre responsabilité.

**Ce qui sort de votre machine**

*Butin* : rien vous concernant. Pas de compte, pas de télémétrie, pas de serveur. Vos sessions restent chez vous. Les deux seules connexions sortantes sont le téléchargement du catalogue d'objets et la consultation des prix du marché, toutes deux vers des sources publiques.

*Rubin* : vos temps de quête partent au serveur pour alimenter le classement. C'est le but de l'outil.

**Sur ce serveur Discord**, la fiche de configuration que vous remplissez est visible de l'équipe seulement, et sert à comprendre vos rapports de bug. Vous pouvez demander sa suppression.
""",
    ),
)


def check() -> list[str]:
    """Offline validation, mirrored by the test suite."""
    problems: list[str] = []
    declared = set(bp.GUIDE_TAGS)

    titles = [g.title for g in GUIDES]
    duplicates = {t for t in titles if titles.count(t) > 1}
    if duplicates:
        problems.append(f"titres de guide en double : {sorted(duplicates)}")

    for guide in GUIDES:
        if len(guide.title) > 100:
            problems.append(f"titre trop long ({len(guide.title)}) : {guide.title}")
        if len(guide.body) > BODY_LIMIT:
            problems.append(
                f"corps trop long ({len(guide.body)}) : {guide.title}"
            )
        unknown = set(guide.tags) - declared
        if unknown:
            problems.append(f"{guide.title} : étiquettes inconnues {sorted(unknown)}")
        if not guide.tags:
            problems.append(f"{guide.title} : aucune étiquette")
    return problems
