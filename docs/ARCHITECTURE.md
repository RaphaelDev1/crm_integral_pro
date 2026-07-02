# Architecture

## Vue d'ensemble

Application monolithique **Streamlit** — un seul processus Python qui sert
à la fois l'UI et la logique métier, avec une base **SQLite** locale en
mode WAL pour supporter plusieurs conseillers connectés en même temps.

```
Navigateur ⇄ Streamlit (src/app.py) ⇄ SQLite (src/ia_conseil_crm.db)
                       │
                       ├─ PyPDF2   → extraction texte des factures PDF
                       └─ fpdf2    → génération des PDF de restitution
                       └─ smtplib  → envoi email au client (config en session)
```

Pas de backend séparé, pas d'API HTTP : Streamlit gère le rendu et l'état
(`st.session_state`) dans le même fichier que les fonctions d'accès BDD.

## Découpage de `src/app.py`

Le fichier est organisé en sections numérotées (commentaires `# N. ...`),
dans l'ordre d'exécution du script :

| # | Section | Rôle |
|---|---------|------|
| 1 | Connexion BDD + WAL | `get_conn()`, création des tables, migrations incrémentales |
| 2 | Authentification | Hash PBKDF2-SHA256, vérification mot de passe |
| 3 | Gestion des utilisateurs | Création compte, admin par défaut |
| 4 | Prospects | CRUD (ajouter / lire / mettre à jour / supprimer) |
| 5 | Clients | CRUD |
| 6 | Contrats | CRUD, liés à un client (`client_id`) |
| 7 | Offres (catalogue) | CRUD + jeu de données de démonstration |
| 8 | Analyse PDF | Extraction facture PDF + parsing speedtest |
| 9 | Moteur de comparaison | Recommandation d'offres + calcul d'économie |
| 10 | Génération PDF | Restitution client (fpdf2) |
| 11 | Email | Envoi SMTP de la restitution |
| 12 | Session state | Valeurs par défaut (`DEFAUTS`), wizard, config |
| 13 | Barre latérale | Login, navigation, métriques rapides |
| 14 | Nouveau diagnostic | Wizard multi-étapes (besoins → recommandation → restitution) |
| 15 | Tableau de bord | **Page d'atterrissage après connexion** |
| 16 | Prospects (UI) | Liste, filtres, relance, conversion en client |
| 17 | Clients & contrats (UI) | Fiche client, contrats associés |
| 18 | Admin (UI) | Utilisateurs, catalogue, config SMTP |
| 19 | Offres de démonstration | Bouton de pré-remplissage du catalogue |

## Navigation

- L'état de navigation vit dans `st.session_state.menu`.
- La sidebar (section 13) affiche un `st.radio` piloté par `options_menu`
  et une garde bloque tout accès (`st.stop()`) tant que
  `auth_logged_in` est faux.
- **Il n'y a plus de page d'accueil séparée** : après connexion (ou après
  déconnexion/reconnexion), l'utilisateur arrive directement sur le
  **Tableau de bord**, qui sert de point d'entrée et de résumé d'activité
  (prospects à relancer, derniers clients, KPIs, vue globale pour les
  Admins).

## Modèle de données

Voir [DATABASE.md](DATABASE.md) pour le détail des tables.

## Sécurité

- Mots de passe hashés en PBKDF2-SHA256 (260k itérations), jamais stockés
  ou loggés en clair.
- Toutes les requêtes SQL avec paramètres dynamiques utilisent des
  placeholders `?` (pas de f-string dans le SQL).
- Les colonnes modifiables dynamiquement (`UPDATE ... SET {champ} = ?`)
  sont validées contre une whitelist (`CHAMPS_PROSPECT`, `CHAMPS_CLIENT`,
  `CHAMPS_CONTRAT`, `CHAMPS_OFFRE`, `CHAMPS_UTILISATEUR`) avant d'être
  interpolées dans la requête, ce qui empêche l'injection SQL via un nom
  de colonne arbitraire.
- Chaque conseiller ne voit que ses propres prospects/clients
  (`cree_par`), sauf bascule explicite en vue globale pour un Admin.

## Limites connues

- Un seul fichier applicatif — acceptable tant que l'équipe reste petite,
  à surveiller si le fichier continue de grossir (voir
  [CONTRIBUTING.md](CONTRIBUTING.md)).
- La configuration SMTP est ressaisie à chaque session (stockée en
  `session_state`, pas persistée) — voir `src/.env.example` pour une piste
  d'évolution.
