# Contributing (notes pour soi-même)

## Avant de coder
- Lire `.claude/quick-context.txt` pour se remettre en tête la structure
  du fichier et les numéros de section.
- Les règles de convention détaillées sont dans `.claude/project.rules.md`.

## Lancer le projet en local

```
cd src
pip install -r requirements.txt
streamlit run app.py
```

## Modifier le schéma de la base

1. Colonne dans `initialiser_bdd()` (nouvelles bases).
2. Entrée dans `_migrer_bdd()` (bases existantes, `ALTER TABLE`).
3. Ajouter au bon `CHAMPS_*` si la colonne doit être éditable.
4. Documenter dans `docs/DATABASE.md`.

## Ajouter une page

1. Ajouter le libellé dans `options_menu` (section 13, sidebar).
2. Ajouter le bloc `elif menu == "...":` correspondant.
3. Vérifier les droits nécessaires (`peut_modifier()` / `est_admin()`).
4. Mettre à jour `docs/ARCHITECTURE.md` (tableau des sections) et
   `.claude/quick-context.txt`.

## Avant de commit

Suivre `.claude/checklist-commits.md`.

## Style

- Français pour les noms de fonctions/variables métier, cohérent avec
  l'existant.
- Pas de nouvelle dépendance sans mise à jour de `src/requirements.txt`.
- Pas de secret en dur — `src/.env.example` documente les variables
  d'environnement envisageables.
