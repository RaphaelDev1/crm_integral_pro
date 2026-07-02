# Règles du projet — CRM Intégral Pro

## Contexte
App interne Streamlit, un seul conseiller ou une petite équipe. Pas de
CI/CD, pas de déploiement cloud pour l'instant. Priorité : robustesse et
simplicité plutôt qu'architecture générique.

## Conventions de code
- Tout le code métier vit dans `src/app.py` — ne pas éclater en modules
  tant que le fichier reste gérable et qu'aucun besoin concret ne l'impose.
- Noms de fonctions et variables en français, cohérent avec le reste du
  fichier (`lire_prospects`, `ajouter_client`, `maj_prospect`, …).
- Toute nouvelle colonne modifiable par un formulaire doit être ajoutée à
  l'ensemble `CHAMPS_*` correspondant (protection contre l'injection SQL
  sur les `UPDATE` dynamiques) — voir en tête de fichier.
- Toute nouvelle colonne BDD s'ajoute dans `initialiser_bdd()` (nouvelle
  installation) **et** dans `_migrer_bdd()` (installations existantes).
- Utiliser `safe_float()` pour toute conversion numérique venant d'un
  formulaire ou d'un import (jamais de `float()` nu sur une entrée user).
- Toujours `st.rerun()` après une mutation BDD suivie d'un changement de
  page/état — un bug historique (page bloquée après création client) a
  été causé par un rerun manquant.

## Sécurité
- Mots de passe : PBKDF2-SHA256, jamais de hash maison, jamais de
  mot de passe en clair en log ou en note.
- Toute requête SQL avec des valeurs dynamiques doit être paramétrée
  (`?`), jamais de f-string dans un `WHERE`/`VALUES`.
- Les noms de colonnes dynamiques (dans les `UPDATE ... SET {col} = ?`)
  doivent systématiquement être validés contre un `CHAMPS_*` whitelist
  avant d'être interpolés dans le SQL.

## Navigation / UI
- Après connexion, l'utilisateur arrive sur le **Tableau de bord**
  (`📊 Tableau de bord`) — il n'y a plus de page d'accueil séparée.
- Le menu actif vit dans `st.session_state.menu` ; toute nouvelle page
  doit être ajoutée à `options_menu` (sidebar) et gérée comme un bloc
  `elif menu == "..."`.
- Chaque conseiller ne voit que ses propres données (`cree_par`) sauf
  bascule explicite en "vue globale" pour un Admin.

## Ce qu'on évite
- Pas d'abstraction/config générique tant qu'un seul cas d'usage existe.
- Pas de dépendance externe ajoutée sans mise à jour de
  `src/requirements.txt`.
- Pas de secret (mot de passe SMTP, etc.) commité en dur — utiliser
  `src/.env.example` comme référence si on bascule vers une config par
  environnement.
