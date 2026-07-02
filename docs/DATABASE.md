# Schéma de base de données

SQLite, mode WAL (`PRAGMA journal_mode=WAL`), clés étrangères activées
(`PRAGMA foreign_keys=ON`). Fichier : `src/ia_conseil_crm.db` (à côté de
`app.py`, chemin résolu via `os.path.dirname(__file__)` donc indépendant
du répertoire de lancement).

Les tables sont créées dans `initialiser_bdd()` ; toute colonne ajoutée
après la première mise en production passe par `_migrer_bdd()`
(`ALTER TABLE ... ADD COLUMN`, échec silencieux si la colonne existe déjà).

## `utilisateurs`

| Colonne | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| username | TEXT UNIQUE NOT NULL | normalisé en minuscules |
| nom_complet | TEXT NOT NULL | |
| password_hash | TEXT NOT NULL | `salt:hash` PBKDF2-SHA256 |
| role | TEXT | `Admin` / `Conseiller` / `Lecture` |
| actif | INTEGER | 1 = compte actif |
| date_creation | TEXT | `dd/mm/YYYY HH:MM` |

Compte admin créé automatiquement au premier lancement si la table est
vide (`creer_admin_par_defaut()`) : `admin` / `Admin2026!`.

## `prospects`

| Colonne | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| ref | TEXT | générée par `generer_ref()` (timestamp + suffixe aléatoire, anti-collision concurrente) |
| prenom, nom | TEXT | |
| telephone, email | TEXT | validés côté UI (`valider_email`, `valider_telephone`), non bloquant |
| code_postal, ville | TEXT | |
| type_client | TEXT | Particulier / Pro |
| univers_interesse | TEXT | sous-ensemble de `UNIVERS` |
| service_principal | TEXT | service demandé en priorité (cross-sell traité séparément) |
| operateur_actuel, offre_actuelle | TEXT | |
| techno | TEXT | FIBRE / ADSL / 5G / 4G |
| data_go | TEXT | |
| cout_mensuel_actuel | REAL | |
| satisfaction_reseau | TEXT | emoji + libellé |
| veut_rester | TEXT | |
| speed_down, speed_up | REAL | issus du speedtest importé |
| cout_elec, cout_gaz | REAL | |
| fournisseur_energie | TEXT | |
| abonnements | TEXT | JSON sérialisé |
| lignes_multi | TEXT | JSON sérialisé (multi-lignes) |
| economie_estimee_an | REAL | calculée par le moteur de comparaison |
| notes | TEXT | auto-enrichies à la création |
| statut | TEXT | défaut `À relancer` |
| date_creation, date_relance | TEXT | |
| cree_par | TEXT | nom du conseiller — filtrage des vues |

Colonnes modifiables via formulaire : voir `CHAMPS_PROSPECT` dans
`app.py`.

## `clients`

Même forme que `prospects` (sans `univers_interesse`, `service_principal`,
`abonnements`, `lignes_multi`, `statut`, `date_relance`) — un prospect
converti devient un client (voir "✅ Converti en client" sur le Tableau
de bord). Colonnes modifiables : `CHAMPS_CLIENT`.

## `contrats`

| Colonne | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| client_id | INTEGER FK → clients(id) | |
| univers, categorie | TEXT | |
| fournisseur, nom_offre | TEXT | |
| cout_mensuel, economie_mensuelle | REAL | |
| reference_contrat | TEXT | |
| statut_contrat | TEXT | |
| date_souscription | TEXT | |
| notes | TEXT | |
| cree_par | TEXT | |

Colonnes modifiables : `CHAMPS_CONTRAT`.

## `offres` (catalogue)

| Colonne | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| univers, categorie, fournisseur, nom_offre | TEXT | |
| prix_mensuel, frais_activation | REAL | |
| engagement_mois | INTEGER | |
| caracteristiques | TEXT | |
| commission_affiliation | REAL | |
| actif | INTEGER | 1 = visible dans les comparaisons |
| date_maj | TEXT | |

Colonnes modifiables : `CHAMPS_OFFRE`. `inserer_offres_demo()` (section 19
de `app.py`) pré-remplit un catalogue de démonstration Télécom / Énergie /
Abonnements depuis Admin.

## Migrations

Toute évolution de schéma suit ce processus (voir aussi
[CONTRIBUTING.md](CONTRIBUTING.md)) :

1. Ajouter la colonne dans le `CREATE TABLE` de `initialiser_bdd()`
   (nouvelles installations).
2. Ajouter une entrée `(table, colonne, type)` dans la liste
   `migrations` de `_migrer_bdd()` (installations existantes).
3. Documenter la colonne dans ce fichier.
4. Ajouter la colonne au bon ensemble `CHAMPS_*` si elle doit être
   modifiable depuis un formulaire.
