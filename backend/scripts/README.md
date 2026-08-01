# Migration SQLite → Postgres

Script à usage unique qui bascule les données du CRM Streamlit (`src/ia_conseil_crm.db`,
SQLite) vers `backend/` (Postgres). À lancer une fois, manuellement, lors du
passage effectif à l'auth/données unifiées côté backend/ (voir le plan
"01 Socle transverse").

## Prérequis

- `backend/.env` configuré avec `DATABASE_URL` pointant vers le Postgres cible.
- Les migrations Alembic à jour (`alembic upgrade head`) — en particulier les
  révisions `0010` à `0013` qui créent `comparaisons_offres`, les tables de
  veille, `documents_prospect` et `parametres`.
- Le stockage S3 configuré (`S3_BUCKET`, etc.) si `documents_prospect` contient
  des fichiers à migrer — sinon repli automatique sur le disque local de dev
  (voir `backend/services/storage_engine.py`), à ne pas utiliser en production.

## Lancement

```bash
python -m backend.scripts.migrer_sqlite_vers_postgres --sqlite-path src/ia_conseil_crm.db
```

## Ce que fait le script

Copie, dans cet ordre (dépendances FK) : `utilisateurs` → `offres` → `clients`
→ `prospects` → `contrats` → `parametres` → `sources_veille` →
`veille_historique_prix`/`veille_alertes` → `documents_prospect`.

Hors périmètre (aucune source SQLite, tables natives backend/) : `dossiers`,
`mandats`, `demarches`, `documents` (KYC), `commissions`, `mandat_honoraires`,
`factures_analysees`, `tokens_publics`.

**Contrats rattachés à un prospect uniquement** (`type_contrat="reference_externe"`,
`client_id` NULL côté SQLite) : ignorés — `backend/models/contrat.py` n'a pas
de colonne `prospect_id`. Comptés et signalés dans la sortie du script.

## Correspondance d'ids

Les deux bases utilisent des entiers auto-incrémentés indépendants : un même
id SQLite/Postgres ne désigne jamais la même ligne. Le script crée et
alimente une table `migration_id_map(entity_type, ancien_id, nouvel_id)`
(hors Alembic, artefact opérationnel — pas de schéma applicatif) qui sert à
la fois de :

- **résolveur de FK** entre entités migrées dans le même run (ex. retrouver
  le nouvel id Postgres d'un client pour migrer ses contrats) ;
- **mécanisme de déduplication** : chaque ligne SQLite est vérifiée dans
  `migration_id_map` avant d'être migrée ; si elle y est déjà, elle est
  ignorée. Le script peut donc être relancé sans risque après un arrêt en
  cours de route (crash, coupure réseau pendant l'upload d'un document...).

Cette table est conservée après la migration (trace d'audit utile en support :
"pourquoi ce client a-t-il l'id 42 côté Postgres ?").

## Garde-fou "usage unique"

Au tout premier lancement (`migration_id_map` vide), le script vérifie que
**toutes** les tables cibles Postgres sont vides et refuse de continuer sinon
— ce n'est pas un outil d'upsert, il ne doit jamais écrire par-dessus des
données réelles déjà présentes côté backend/. Une fois `migration_id_map`
non vide, cette vérification est sautée (on est en reprise) : la
déduplication ligne par ligne prend le relais.

## Cohabitation avec le mirroring paresseux (`_backend_client_id_pour`)

`src/api_client.py::_backend_client_id_pour()` crée déjà, à la volée, un
client Postgres miroir dès qu'un dossier/mandat/démarche est créé depuis
Streamlit — et note l'id obtenu dans `clients.backend_client_id`/
`prospects.backend_client_id` côté SQLite.

Le script respecte ce mécanisme :
- si `backend_client_id` est déjà renseigné sur une ligne `clients`/`prospects`,
  il **réutilise cet id** (pas de nouvelle ligne Postgres créée) et se contente
  d'enregistrer le mapping ;
- sinon, il crée la ligne Postgres puis **réécrit `backend_client_id` côté
  SQLite** avec le nouvel id — pour qu'après la migration,
  `_backend_client_id_pour()` prenne sa branche "rafraîchir" (PUT) au lieu de
  "créer" (POST) et n'engendre pas de doublon.

## Documents prospect (facture/speedtest)

Étape la plus lente et la plus susceptible d'échouer partiellement (un appel
S3 par fichier). Contrairement aux autres étapes (un commit par table), celle-ci
committe **ligne par ligne** : un échec sur le fichier N ne remet pas en cause
les N-1 déjà migrés, et un relancement du script reprend exactement où il
s'est arrêté grâce à la déduplication par `migration_id_map`.

---

# Seed admin

Équivalent Postgres de `src/auth.py::creer_admin_par_defaut()` : crée un
compte `admin` (rôle Admin, `doit_changer_mdp=True`) si la table
`utilisateurs` est vide. Nécessaire pour se connecter à `frontend-conseiller/`
sur une base backend/ neuve — sans lui, aucun moyen de créer le tout premier
utilisateur (pas d'endpoint d'inscription, par design).

```bash
python -m backend.scripts.seed_admin
```

Affiche le mot de passe généré en clair **une seule fois** (à noter
immédiatement) ; ne fait rien (idempotent) si un compte existe déjà.
