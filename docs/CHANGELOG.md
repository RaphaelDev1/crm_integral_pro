# Changelog

## 2026-07-02

- Réorganisation du projet : le code applicatif passe de
  `crm_integral_pro.py` (racine) à `src/app.py`, la base SQLite le suit
  dans `src/ia_conseil_crm.db`.
- Le chemin de la base est désormais résolu relativement à `app.py`
  (`os.path.dirname(__file__)`) au lieu d'un chemin relatif au répertoire
  de lancement.
- Ajout de `docs/` (architecture, API, base de données, contribution) et
  de `.claude/` (contexte, règles, checklist, prompts types).
- **Suppression de la page d'accueil** (`🏠 Accueil`) : après connexion,
  l'utilisateur arrive directement sur le **Tableau de bord**, qui devient
  la page d'atterrissage par défaut (y compris après déconnexion/
  reconnexion).

## Étape 2 — Fiabiliser l'existant

- Bug critique : `st.rerun()` manquant en fin d'étape 5 du wizard (page
  bloquée après création client).
- Bug : `generer_ref()` pouvait produire des doublons en accès concurrent.
- Bug : calcul d'économie des abonnements ignorait le coût client réel.
- Validation email + téléphone avant enregistrement.
- `safe_float()` — conversions numériques protégées, plus de crash.
- Spinner sur les opérations lentes (comparaison, génération PDF).
- Filtre par statut sur la page Prospects.
- Confirmation avant suppression prospect / client.
- Affichage propre quand la recherche client ne retourne rien.
- Notes auto-enrichies à la création.

## Étape 1 — Fondations solides

- Mode WAL SQLite, comptes nominatifs, rôles, traçabilité, sécurité SQL
  (whitelists `CHAMPS_*`, requêtes paramétrées).
