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
Les salons **français et anglais** sont ouverts à tout le monde, écrivez dans la langue qui vous arrange.

**🇬🇧 English**
This is the server of two free tools for Black Desert Online, on PC:

> 🪙 **Butin** — the loot tracker. It reads the game log and counts your drops live, with prices and post-tax value. Its interface is in French.
> ⏱️ **Rubin** — the quest timer. It reads the quest banner and times your runs. French first, English later.

Bug reports and ideas are welcome. **French and English channels are open to everyone**, use whichever suits you.
"""

RULES_TITLE = "Règlement / Rules"

RULES_BODY = """\
**🇫🇷**
1. Restez corrects. Pas d'insulte, pas de harcèlement, pas de contenu haineux.
2. Pas de publicité ni de démarchage en message privé.
3. Rien d'illégal, et rien qui enfreint les conditions d'utilisation de Black Desert : pas d'automatisation d'entrées clavier ou souris, pas de bot de jeu, pas de vente de compte.
4. Un sujet par fil dans les salons de bugs et d'idées. Cherchez avant de créer un doublon.
5. Le français et l'anglais sont acceptés partout.

**🇬🇧**
1. Be civil. No insults, harassment or hate speech.
2. No advertising, no DM soliciting.
3. Nothing illegal, and nothing against the Black Desert terms of service: no input automation, no game bot, no account trading.
4. One topic per thread in the bug and idea channels. Search before opening a duplicate.
5. French and English are welcome everywhere.

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
    "1. J'ouvre l'application\n2. Je lance une session\n3. Je ramasse un objet\n"
    "Ce que j'attendais :\nCe qui se passe :"
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

**Étapes pour reproduire / Steps to reproduce**
{steps}
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
# Staff log
# --------------------------------------------------------------------------- #

LOG_REPORT = "📥 **{kind}** · {product} · par {author} · {link}"
LOG_ISSUE_OK = "🔗 Issue GitHub créée : {url}"
LOG_ISSUE_FAIL = "⚠️ Création d'issue GitHub échouée pour {link} : {error}"
