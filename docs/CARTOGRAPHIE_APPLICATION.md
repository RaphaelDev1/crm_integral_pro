# Cartographie de l'application — IA Conseil / CRM Intégral Pro

Ce document retrace l'ensemble de l'application : ce qu'elle fait, comment elle est construite, et pourquoi elle existe aujourd'hui sous **trois générations qui coexistent**. Il sert de carte de référence avant de lire le détail des autres docs (`docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/API.md`, ainsi que `frontend-conseiller/FRONTEND_CONSEILLER.md` et `docs/MIGRATION_STREAMLIT_VERS_FRONTEND_CONSEILLER.md`).

## 1. Ce que fait l'application

C'est l'outil métier d'un cabinet de conseil qui aide des particuliers/pros à **réduire leurs factures télécom, énergie et abonnements** :

- diagnostic complet d'un prospect (offre actuelle, débit, satisfaction) ;
- comparateur qui recommande de meilleures offres et estime l'économie annuelle ;
- suivi du prospect jusqu'à la signature (scoring, relances, conversion en client) ;
- gestion du dossier de souscription (documents, mandat de résiliation/signature, démarches administratives, activation) ;
- facturation des honoraires du cabinet ;
- veille automatique des prix fournisseurs et alertes si une offre moins chère apparaît ;
- portail self-service pour que le client final dépose ses documents et suive son dossier sans compte ;
- chatbot public de qualification de lead.

## 2. Les trois générations qui coexistent

| Génération | Dossier | Stack | Rôle | Statut |
|---|---|---|---|---|
| **1. Legacy** | `src/` | Streamlit + SQLite (WAL) | Application complète historique, utilisée en production par les conseillers | En service, encore la référence fonctionnelle |
| **2. Backend cible** | `backend/` | FastAPI + Postgres (async SQLAlchemy) + Celery/Redis | API métier propre, découplée, avec workflow de dossier, stockage S3, signature électronique, LRE | En construction active, une partie des fonctionnalités legacy y a déjà été portée |
| **3. Frontends Next.js** | `frontend-conseiller/`, `frontend-portail/` | Next.js 14 | Nouvelles interfaces qui consomment `backend/` | `frontend-portail` est livré et fonctionnel ; `frontend-conseiller` n'est encore qu'un **squelette** (socle technique posé, pages vides) |

Autrement dit : le produit vit aujourd'hui dans `src/` (Streamlit), et le projet est en train de reconstruire progressivement la même chose (et plus) en `backend/` + `frontend-conseiller/`. Voir `docs/MIGRATION_STREAMLIT_VERS_FRONTEND_CONSEILLER.md` pour le plan précis de bascule.

Point important : `src/app.py` (Streamlit) ne parle **pas uniquement** au nouveau backend. Via `src/api_client.py`, il parle à **deux APIs différentes** :
- `crm_api.py` (SQLite, port 8003) pour prospects/clients/contrats/offres — l'API interne historique ;
- `backend/main.py` (Postgres, port 8000) pour dossiers/factures/honoraires/portail — le nouveau backend.

Avec un **disjoncteur** (`_ApiIndisponible`, 20s de cooldown) : si une des deux API ne répond pas, Streamlit retombe automatiquement sur les fonctions `*_engine.py` locales (accès direct SQLite), pour ne jamais planter en prod.

## 3. Application legacy — `src/` (Streamlit)

Interface unique dans `src/app.py` (~220 Ko), pilotée par un menu (`st.session_state.menu`) avec ces sections :

- **🧭 Nouveau diagnostic** — assistant en 4 étapes (univers → identité → situation actuelle → recommandations télécom/énergie/abonnements) → restitution PDF/email.
- **📊 Tableau de bord** — relances en retard/du jour/à venir, KPIs.
- **📇 Prospects** — liste, édition, scoring, conversion en client, suppression.
- **👥 Clients & contrats** — fiches clients et contrats associés.
- **🧾 Facturation** — devis d'honoraires, mandat, suivi de paiement.
- **🛠️ Admin** (réservé admin) — utilisateurs, catalogue d'offres, ajout d'offre, données de démo, email, facturation, OCR de factures (Vision), veille prix (sources / alertes / historique).

**Modules métier (`src/*_engine.py`)**, appelés via `src/api_client.py` :
- `clients_engine.py` — CRUD clients, note de couverture réseau par zone, widget de relance.
- `prospects_engine.py` — CRUD prospects, **scoring de lead** (`calculer_score_prospect`), tokens d'upload de documents, coût de référence par catégorie.
- `offres_engine.py` — moteur de comparaison d'offres.
- `contrats_engine.py`, `facturation_engine.py`, `souscription_engine.py`.
- `pdf_engine.py` — génération de PDF et OCR de factures.
- `email_engine.py` / `sms_engine.py` / `notifications.py` — envoi et digests programmés.
- `veille_prix_engine.py` — scraping de prix concurrents.
- `catalogue_engine.py` — catalogue d'offres auto-alimenté.
- `audit_agent.py` — agent d'audit autonome.
- `jwt_auth.py` / `auth.py` — hash de mot de passe + verrouillage après échecs de connexion.

**Persistance** : `src/db.py`, SQLite en mode WAL (`src/ia_conseil_crm.db`), avec recherche plein texte (FTS) et journal d'audit générique (`enregistrer_action` / `lire_historique`).

**API interne** : `src/crm_api.py` — API REST JWT sur SQLite (port 8003), consommée par Streamlit pour prospects/clients/contrats/offres.

**Chatbot public** : `src/chatbot_api.py` — process FastAPI séparé (port 8001), widget JS public (`src/static/chatbot_widget.js`), utilise Claude (tool-use) pour qualifier un lead, comparer des offres, faire un bilan, avec limiteur de débit par IP. Expose aussi un mini "portail prospect" par token, distinct de `frontend-portail`.

## 4. Backend cible — `backend/` (FastAPI + Postgres)

`backend/main.py` : `FastAPI(title="IA Conseil — API")`, Sentry si configuré, CORS restreint au portail client + `localhost:3000`, aucune création de table auto (schéma géré uniquement par Alembic), endpoint `/health`.

### Routers (`backend/routers/`)

| Router | Ressource | Auth |
|---|---|---|
| `auth.py` | login, refresh, mot de passe oublié/reset, `/me` | public (login) puis JWT |
| `clients.py` | CRUD clients + briefing | JWT |
| `prospects.py` | CRUD prospects + documents | JWT |
| `dossiers.py` | CRUD dossier, transitions d'état, timeline, notes, lien client, PDF restitution | JWT |
| `factures.py` | analyse de facture uploadée | JWT |
| `honoraires.py` | mandat d'honoraires (CRUD + signature) | JWT |
| `demarches.py` | démarches administratives (génération, envoi, remplissage, documents) | JWT |
| `comparaisons_offres.py` | enregistrements de comparaison d'offres | JWT |
| `offres.py` | `/offres/comparer`, `/offres/recommandations` | JWT |
| `veille.py` | sources de veille prix, historique, alertes, déclenchement manuel | JWT admin |
| `alertes_offres.py` | valider/rejeter une alerte d'offre moins chère | JWT |
| `parametres.py` | réglages + logo | JWT admin |
| `portail_public.py` | contexte dossier, upload doc, suivi, démarches, speedtest — **par token, sans compte** | public |
| `speedtest_backend.py` | backend du test de débit (garbage/empty/upload/getIP) | public |
| `webhooks.py` | webhook Yousign (signature électronique) | public |

### Modèles (`backend/models/`)

`User`, `Client`, `Prospect`, `Dossier`, `Demarche`, `Document`, `DocumentProspect`, `Contrat`, `Mandat`, `MandatHonoraires`, `Offre`, `ComparaisonOffre`, `AlerteOffre`, `Commission`, `Abonnement`, `FactureAnalyse`, `Parametre`, `TokenPublic`, `LoginTentative`, `SourceVeille`/`VeilleHistoriquePrix`/`VeilleAlerte`.

Important : `Client` et `Prospect` sont explicitement documentés comme des **miroirs** des tables SQLite historiques (`src/db.py`), y compris le champ `score` du prospect — signe que le backend est pensé pour remplacer `src/db.py` à terme, colonne par colonne.

### Logiques métier clés (`backend/services/`)

- **`dossier_engine.py`** — machine à états stricte du parcours de souscription :
  `initie → docs_demandes → docs_recus → mandat_a_signer → mandat_signe → soumis_fournisseur → en_activation → actif → facture`, avec états terminaux `echec`/`annule`. Fonctions : `peut_transiter`, `transiter`, `construire_timeline`, `dossiers_stagnants`.
- **`notification_engine.py`** — email réel (Resend) et SMS (OVH/Twilio), avec repli silencieux si non configuré.
- **`storage_engine.py`** — stockage documentaire S3-compatible (Scaleway), chiffrement SSE-S3, URLs signées, clés non devinables, fallback disque local en dev.
- **`token_engine.py`** — tokens de lien client public (`secrets.token_urlsafe(32)`, expiration, verrouillage IP optionnel, révocation).
- `alertes_offres_engine.py`, `demarches_engine.py`, `dossier_notifications.py`, `facture_analyzer.py`, `kyc_engine.py`, `lre_engine.py` (lettre recommandée électronique via un service type AR24), `offres_engine.py`, `restitution_pdf_engine.py`, `signature_engine.py` (Yousign), `veille_engine.py`.

### Traitements asynchrones (`backend/workers/tasks.py`, Celery)

`valider_document_kyc`, `envoyer_mandat_signature` / `telecharger_mandat_signe` (Yousign), `relancer_dossiers_stagnants`, `generer_document_demarche`, `envoyer_demarche_lre` / `verifier_accuses_lre_en_attente`, `lancer_veille_periodique`, `detecter_offres_moins_cheres_periodique`, `envoyer_digest_quotidien`. Chaque tâche encapsule son code async via `asyncio.run` (un worker Celery n'a pas de boucle événementielle).

### Sécurité (`backend/core/security.py`)

JWT (PyJWT, HS256), hash de mot de passe PBKDF2-SHA256 (260k itérations), types de tokens `access`/`refresh`/`reset` (`TokenType`), dépendances FastAPI `get_current_user` / `require_role(*roles)`, limitation des tentatives de connexion (5 essais / 15 min). C'est le portage propre de `src/auth.py` / `src/jwt_auth.py`.

### Infra (`docker-compose.yml` racine)

Services : `redis`, `postgres` (profil optionnel, sinon Neon en cloud), `backend` (uvicorn --reload, :8000), `celery-worker`, `celery-beat`, `flower` (:5555), `streamlit` (:8501).

## 5. Frontends Next.js

### `frontend-portail/` — portail client (livré)

Accès **sans compte**, par lien à token (`/dossier/[token]`) : contexte du dossier, économie annuelle estimée, checklist de documents à fournir, sous-pages `documents/`, `demarches/`, `speedtest/`. Appelle directement `backend/routers/portail_public.py` en `fetch` côté client (`lib/api.ts`), pas de BFF car pas d'authentification à protéger — la sécurité repose sur le token non devinable (`token_engine.py`).

### `frontend-conseiller/` — outil conseiller (squelette)

Interface interne authentifiée destinée à remplacer Streamlit pour les conseillers. Voir `frontend-conseiller/FRONTEND_CONSEILLER.md` pour le détail : à ce stade, seul le **socle technique** (auth JWT via BFF, layout, 6 pages stub) est livré ; le contenu métier reste à construire — c'est l'objet du plan de migration.

## 6. Flux de données — vue d'ensemble

```
                     ┌───────────────────────────┐
                     │   Conseiller (interne)     │
                     └─────────────┬─────────────┘
                                   │
        ┌──────────────────────┐  │  ┌──────────────────────────┐
        │  src/app.py           │◄─┼─►│ frontend-conseiller/       │
        │  (Streamlit, legacy)  │  │  │ (Next.js, squelette)       │
        └──────┬─────────┬─────┘  │  └──────────────┬─────────────┘
               │         │                            │ BFF (cookies HttpOnly)
        ┌──────▼───┐ ┌───▼────────────┐               │
        │crm_api.py│ │ backend/main.py│◄──────────────┘
        │ SQLite   │ │ FastAPI+Postgres│
        │ :8003    │ │ :8000           │
        └──────────┘ └───────┬─────────┘
                              │
                     ┌────────┴────────┐
                     │ Celery + Redis   │  (relances, veille, LRE, signature)
                     └─────────────────┘
                              │
                     ┌────────▼────────┐
                     │  frontend-portail│  (client final, sans compte, via token)
                     └─────────────────┘
```

## 7. Pour aller plus loin

- Détail technique legacy Streamlit : `docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/API.md`, `IA.CONSEIL.MD`, `IA_CONSEIL_UTILISATION.md`.
- Roadmap produit : `IA_CONSEIL_ROADMAP.md`, `ROADMAP_EXECUTION.md`.
- Ce qu'il reste à faire côté frontend conseiller : `frontend-conseiller/FRONTEND_CONSEILLER.md` et `docs/MIGRATION_STREAMLIT_VERS_FRONTEND_CONSEILLER.md`.
