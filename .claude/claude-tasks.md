# Tâches Claude typiques — prompts prêts à l'emploi

## Ajouter un champ à un prospect/client
> "Ajoute un champ `<nom_champ>` (type `<TEXT/REAL>`) aux prospects et
> clients : colonne BDD (initialiser_bdd + _migrer_bdd), ensemble
> CHAMPS_PROSPECT/CHAMPS_CLIENT, champ dans le formulaire wizard et dans
> l'édition Prospects/Clients. Mets à jour docs/DATABASE.md."

## Ajouter une nouvelle page au menu
> "Ajoute une page `<Nom>` : entrée dans options_menu (sidebar), bloc
> `elif menu == "<Nom>":`, rôle minimum requis si besoin (peut_modifier /
> est_admin). Mets à jour .claude/quick-context.txt et docs/ARCHITECTURE.md."

## Debugger un crash Streamlit
> "Voici la stack trace : <coller>. Trouve la section concernée dans
> src/app.py (voir la numérotation des sections dans
> .claude/quick-context.txt) et corrige sans casser le flux existant."

## Revoir la sécurité d'une requête SQL
> "Relis les fonctions CRUD de <table> dans src/app.py : vérifie que
> toute valeur dynamique est paramétrée et que les noms de colonnes
> dynamiques passent par un CHAMPS_* whitelist."

## Préparer une release
> "Mets à jour docs/CHANGELOG.md avec les changements depuis la dernière
> entrée, en te basant sur les diffs. Vérifie la checklist dans
> .claude/checklist-commits.md."
