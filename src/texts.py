"""Every user-facing string, bilingual FR / EN.

Kept in one module so the wording can be reviewed without reading the logic,
and so a translation mistake is a one-line fix.
"""

from __future__ import annotations

WELCOME_TITLE = "Bienvenue / Welcome"

WELCOME_BODY = """\
**🇫🇷 Français**
Ce serveur est celui de deux outils gratuits pour Black Desert Online, sur PC :

> 🪙 **Butin** — le suivi de butin. Il lit le journal de jeu et compte vos drops en direct, avec les prix et le net après taxe.
> ⏱️ **Rubin** — le chronomètre de quêtes. Il lit le bandeau de quête et mesure le temps que vous mettez.

Ici on parle des deux, on remonte les bugs, on propose des idées, et on partage ses sessions.
**Avant de poser une question, passez par les guides** : installation, calibrage et dépannage y sont, un fil par sujet, filtrable par logiciel.
**Écrivez dans la langue qui vous arrange**, français ou anglais : le salon de discussion est commun.

**🇬🇧 English**
This is the server of two free tools for Black Desert Online, on PC:

> 🪙 **Butin** — the loot tracker. It reads the game log and counts your drops live, with prices and post-tax value. Its interface is in French.
> ⏱️ **Rubin** — the quest timer. It reads the quest banner and times your runs. French first, English later.

Bug reports and ideas are welcome. **Check the guides first**: install, calibration and troubleshooting live there, one thread per topic, filterable by tool.
**Write in whichever language suits you**, French or English: there is one shared chat channel, not one per language.
"""

RULES_TITLE = "Règlement / Rules"

RULES_BODY = """\
**🇫🇷**
1. Restez corrects. Pas d'insulte, pas de harcèlement, pas de contenu haineux.
2. Pas de publicité ni de démarchage en message privé.
3. Rien d'illégal, et rien qui enfreint les conditions d'utilisation de Black Desert : pas d'automatisation d'entrées clavier ou souris, pas de bot de jeu, pas de vente de compte.
4. Un sujet par fil dans les salons de bugs et d'idées. Cherchez avant de créer un doublon.
5. Le français et l'anglais sont acceptés partout, y compris dans le salon de discussion.

**🇬🇧**
1. Be civil. No insults, harassment or hate speech.
2. No advertising, no DM soliciting.
3. Nothing illegal, and nothing against the Black Desert terms of service: no input automation, no game bot, no account trading.
4. One topic per thread in the bug and idea channels. Search before opening a duplicate.
5. French and English are welcome everywhere, the chat channel included.

*Les deux outils lisent l'écran, ils ne touchent jamais au jeu ni à sa mémoire. / Both tools read the screen only, they never touch the game or its memory.*
"""

# --------------------------------------------------------------------------- #
# Support panel (the message carrying the buttons)
# --------------------------------------------------------------------------- #

PANEL_TITLE = "{emoji} {label} — signaler un bug ou proposer une idée"

PANEL_BODY = """\
**🇫🇷** Utilisez les boutons ci-dessous. Un formulaire s'ouvre, il crée un fil au bon endroit avec votre version et votre système, et l'équipe est prévenue.
**🇬🇧** Use the buttons below. A form opens, it creates a thread in the right place with your version and OS, and the team is notified.

*Un bug rapporté avec la version et les étapes exactes est corrigé dix fois plus vite. / A report with the version and exact steps gets fixed ten times faster.*
"""

BTN_BUG = "🐛 Signaler un bug / Report a bug"
BTN_IDEA = "💡 Proposer une idée / Suggest an idea"

# --------------------------------------------------------------------------- #
# Bug modal
# --------------------------------------------------------------------------- #

MODAL_BUG_TITLE = "{label} — bug"
FIELD_SUMMARY_LABEL = "Résumé en une phrase / One-line summary"
FIELD_SUMMARY_PLACEHOLDER = "Le compteur reste à zéro pendant le farm"
FIELD_VERSION_LABEL = "Version du logiciel / Software version"
FIELD_VERSION_PLACEHOLDER = "visible en bas de la fenêtre, ex. 1.4.2"
FIELD_SYSTEM_LABEL = "Système / Operating system"
FIELD_STEPS_LABEL = "Étapes pour reproduire / Steps to reproduce"
FIELD_STEPS_PLACEHOLDER = (
    "1. J'ouvre l'appli\n2. Je lance une session\n3. Je ramasse un objet\n"
    "Attendu :\nObtenu :"
)

# --------------------------------------------------------------------------- #
# Idea modal
# --------------------------------------------------------------------------- #

MODAL_IDEA_TITLE = "{label} — idée / idea"
FIELD_IDEA_LABEL = "Votre idée en une phrase / Your idea"
FIELD_IDEA_PLACEHOLDER = "Exporter la session en tableur"
FIELD_PROBLEM_LABEL = "Le problème que ça résout / The problem"
FIELD_PROBLEM_PLACEHOLDER = (
    "Décrivez ce qui vous bloque aujourd'hui, pas seulement la solution."
)

# --------------------------------------------------------------------------- #
# Thread content
# --------------------------------------------------------------------------- #

THREAD_BUG_BODY = """\
**Rapporté par / Reported by** {author}
**Version** {version}
**Système / OS** {system}
{setup}
**Étapes pour reproduire / Steps to reproduce**
{steps}
"""

#: Inserted into THREAD_BUG_BODY when the reporter has a setup card.
THREAD_BUG_SETUP = """\
{lines}
"""

THREAD_IDEA_BODY = """\
**Proposé par / Suggested by** {author}

**Le problème / The problem**
{problem}

*Réagissez avec 👍 si vous voulez la même chose. / React with 👍 if you want this too.*
"""

ACK_BUG = (
    "✅ Merci, votre bug est ici : {link}\n"
    "Thanks, your report is here: {link}"
)
ACK_IDEA = (
    "✅ Merci, votre idée est ici : {link}\n"
    "Thanks, your idea is here: {link}"
)
ACK_GITHUB = "\nSuivi GitHub / GitHub tracking: {issue_url}"

ERR_NO_CHANNEL = (
    "❌ Le salon de destination est introuvable. Prévenez le staff.\n"
    "The destination channel is missing. Please ping the staff."
)
ERR_GENERIC = (
    "❌ Quelque chose a cassé de mon côté, rien n'est perdu, réessayez dans un instant.\n"
    "Something broke on my side, nothing is lost, try again in a moment."
)

# --------------------------------------------------------------------------- #
# GitHub issue body
# --------------------------------------------------------------------------- #

ISSUE_BUG_BODY = """\
Reported on Discord by **{author}**.

| | |
|---|---|
| Version | {version} |
| OS | {system} |
{setup_rows}
### Summary
{summary}

### Steps to reproduce
{steps}

---
Discord thread: {thread_url}
"""

ISSUE_IDEA_BODY = """\
Suggested on Discord by **{author}**.

### Idea
{summary}

### Problem it solves
{problem}

---
Discord thread: {thread_url}
"""

# --------------------------------------------------------------------------- #
# Setup card (screen + machine)
# --------------------------------------------------------------------------- #

SETUP_PANEL_TITLE = "🖥️ Ma configuration / My setup"

SETUP_PANEL_BODY = """**🇫🇷** Butin et Rubin **lisent votre écran**. Le même exécutable ne se comporte pas pareil en 1920x1080 à 100 % et en 2560x1440 à 150 %, ni en plein écran et en fenêtré. L'échelle de l'interface du jeu compte autant : elle change la taille du texte à lire.

Remplissez cette fiche **une seule fois**. Elle sera jointe automatiquement à tous vos rapports de bug, et vous n'aurez plus jamais à redonner ces informations.

**🇬🇧** Butin and Rubin **read your screen**. The same build behaves differently at 1920x1080 100% and at 2560x1440 150%, and differently again in fullscreen versus borderless. The game's own interface scale matters just as much: it changes the size of the text being read.

Fill this in **once**: it gets attached to every bug report you send afterwards.
"""

BTN_SETUP_SCREEN = "🖥️ Mon écran et mon jeu / My screen"
BTN_SETUP_MACHINE = "⚙️ Ma machine / My PC"
BTN_SETUP_SHOW = "👁️ Voir ma config / Show my setup"

MODAL_SCREEN_TITLE = "Mon écran et mon jeu / Screen"
MODAL_MACHINE_TITLE = "Ma machine / My PC"

FIELD_RESOLUTION_LABEL = "Résolution écran / Screen resolution"
FIELD_RESOLUTION_PLACEHOLDER = "2560x1440"
FIELD_SCALING_LABEL = "Échelle Windows / Windows scaling"
FIELD_SCALING_PLACEHOLDER = "Choisissez / Pick one"
FIELD_SCALING_HINT = "Paramètres Windows > Système > Affichage > Échelle"
FIELD_UI_SCALE_LABEL = "Échelle de l'interface (jeu)"
FIELD_UI_SCALE_PLACEHOLDER = "ex. 90, 100, 110 (Options > Écran)"
FIELD_DISPLAY_MODE_LABEL = "Affichage du jeu / Game display mode"
FIELD_DISPLAY_MODE_PLACEHOLDER = "Choisissez / Pick one"
FIELD_GAME_LANGUAGE_LABEL = "Langue du jeu / Game language"
FIELD_GAME_LANGUAGE_PLACEHOLDER = "Choisissez / Pick one"

FIELD_CPU_LABEL = "Processeur / CPU"
FIELD_CPU_PLACEHOLDER = "Ryzen 5 5600"
FIELD_GPU_LABEL = "Carte graphique / Graphics card"
FIELD_GPU_PLACEHOLDER = "RTX 3060"
FIELD_RAM_LABEL = "Mémoire vive / RAM"
FIELD_RAM_PLACEHOLDER = "16 Go"

SETUP_CARD = """\
**Configuration de {author}**
{lines}

*Mise à jour / Updated: {updated}*
"""

SETUP_SAVED = (
    "✅ Fiche enregistrée. Elle sera jointe à vos prochains rapports.\n"
    "Setup saved. It will be attached to your next reports."
)
SETUP_EMPTY = (
    "Vous n'avez pas encore de fiche. Le bouton « Mon écran et mon jeu » "
    "est dans {channel}.\n"
    "You have no setup yet, the \"My screen\" button is in {channel}."
)
SETUP_MISSING_IN_REPORT = (
    "\n*Pas de fiche de configuration. / No setup on file.*"
)

# --------------------------------------------------------------------------- #
# Screenshots
# --------------------------------------------------------------------------- #

SCREENSHOT_ASK = """\
**🇫🇷** Ajoutez une **capture d'écran** dans ce fil, elle vaut dix lignes de description.
Glissez l'image ici, ou `Impr. écran` puis `Ctrl+V`. Pour Butin, cadrez la **fenêtre du jeu entière**, pas seulement le compteur : le calibrage dépend de ce qu'il y a autour.
Une vidéo courte marche aussi si le problème bouge.

**🇬🇧** Drop a **screenshot** in this thread, it is worth ten lines of text.
Drag the image here, or `PrtScn` then `Ctrl+V`. For Butin, frame the **whole game window**, not just the counter: calibration depends on the surroundings.
A short video works too if the problem moves.
"""

SCREENSHOT_THANKS = (
    "📎 Capture bien reçue, merci. / Screenshot received, thank you."
)

LOG_SCREENSHOT = "📎 Capture ajoutée à {link} par {author}"

# --------------------------------------------------------------------------- #
# Status board
# --------------------------------------------------------------------------- #

STATUS_TITLE = "{dot} {headline}"

LOG_STATUS_CHANGE = "{dot} **{label}** : {before} → {after}{note}"

# --------------------------------------------------------------------------- #
# Versions
# --------------------------------------------------------------------------- #

VERSION_TITLE = "📦 Dernières versions / Latest versions"
VERSION_LINE = "{emoji} **{label}** — `{tag}` · [télécharger / download]({url}) {stamp}"
VERSION_LINE_ERROR = "{emoji} **{label}** — indisponible / unavailable ({error})"
VERSION_FOOTER = (
    "\n*Le numéro de version est en bas de la fenêtre du logiciel. "
    "/ The version number is at the bottom of the app window.*"
)

# --------------------------------------------------------------------------- #
# Arrivals
# --------------------------------------------------------------------------- #

WELCOME_MEMBER = """\
Bienvenue {mention} 👋

Deux outils gratuits pour Black Desert, sur PC : 🪙 **Butin** compte votre butin en direct, ⏱️ **Rubin** chronomètre vos quêtes.

**Pour démarrer** : les guides d'installation et de calibrage sont dans {guides}.
**Un bug ?** Remplissez d'abord votre fiche de configuration dans un salon d'aide : elle sera jointe à tous vos rapports, et sans elle un souci de lecture d'écran est indevinable.

*Welcome! Both tools are French-first but English is welcome here. Install guides are in {guides}.*
"""

# --------------------------------------------------------------------------- #
# Tester role
# --------------------------------------------------------------------------- #

TESTER_GIVEN = "✅ {member} a maintenant le rôle **{role}** et voit la catégorie bêta."
TESTER_REMOVED = "✅ {member} n'a plus le rôle **{role}**."
TESTER_NO_ROLE = (
    "❌ Le rôle **{role}** n'existe pas. Lancez `/setup` d'abord."
)
TESTER_FORBIDDEN = (
    "❌ Je ne peux pas modifier les rôles de cette personne. "
    "Vérifiez que mon rôle est **au-dessus** de `{role}` dans la liste."
)

# --------------------------------------------------------------------------- #
# Setup preflight
# --------------------------------------------------------------------------- #

PREFLIGHT_BLOCKED = """\
❌ **Je ne peux pas construire le serveur, il me manque des droits.**

{problems}

Dans *Paramètres du serveur → Rôles*, donnez au bot un rôle **Administrateur** et
**remontez-le tout en haut de la liste**, puis relancez `/setup`.
"""
PREFLIGHT_MISSING_PERM = "• permission manquante : **{name}**"
PREFLIGHT_LOW_ROLE = (
    "• mon rôle est placé **trop bas** : je ne peux pas gérer les rôles situés au-dessus du mien"
)

# --------------------------------------------------------------------------- #
# Beta welcome
# --------------------------------------------------------------------------- #

BETA_WELCOME_TITLE = "🧪 Bêta / Beta"

BETA_WELCOME_BODY = """\
**🇫🇷**
Vous voyez ces salons parce que vous avez le rôle **Tester**. Ce que ça implique :

> Les versions postées ici **ne sont pas finies**. Elles peuvent compter faux, planter, ou repartir de zéro. Ne les utilisez pas pour une session dont le résultat compte.
> Ce qui est dit ici reste ici tant que la version n'est pas publique.
> Le plus utile n'est pas « ça marche pas », c'est **votre config + ce que vous faisiez + une capture**.

Commencez par remplir votre fiche dans le salon des configs, c'est ce qui rend vos retours exploitables.

**🇬🇧**
You see these channels because you have the **Tester** role. What it means:

> Builds posted here **are not finished**. They may miscount, crash, or be scrapped. Do not use them for a session whose result matters.
> What is said here stays here until the build is public.
> The most useful report is not "it doesn't work", it is **your setup + what you were doing + a screenshot**.

Start by filling in your setup card, that is what makes your feedback usable.
"""

# --------------------------------------------------------------------------- #
# Staff log
# --------------------------------------------------------------------------- #

LOG_REPORT = "📥 **{kind}** · {product} · par {author} · {link}"
LOG_ISSUE_OK = "🔗 Issue GitHub créée : {url}"
LOG_ISSUE_FAIL = "⚠️ Création d'issue GitHub échouée pour {link} : {error}"
