# Cartographie de l'application — IA Conseil / CRM Intégral Pro

Ce document retrace l'ensemble de l'application : ce qu'elle fait, comment elle est construite, et la structure des dossiers. Il sert de carte de référence avant de lire le détail des autres docs (`docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/API.md`, `IA.CONSEIL.MD`, `frontend-conseiller/FRONTEND_CONSEILLER.md`, `docs/MIGRATION_STREAMLIT_VERS_FRONTEND_CONSEILLER.md`).

> **Mise à jour de ce document (02/09/2026)** : la version précédente décrivait `frontend-conseiller` comme un simple squelette avec des pages vides. Ce n'est plus le cas — voir §5. Les sections ci-dessous reflètent l'état réel du code à cette date.

## 1. Ce que fait l'application

C'est l'outil métier d'un cabinet de conseil qui aide des particuliers/pros à **réduire leurs factures télécom, énergie et abonnements** :

- diagnostic complet d'un prospect (offre actuelle, débit, satisfaction réseau), avec import automatique de factures (OCR/LLM) ;
- comparateur qui recommande de meilleures offres et estime l'économie annuelle, univers par univers (Télécom, Énergie, Abonnements) ;
- suivi du prospect jusqu'à la signature (scoring de priorité, relances programmées, conversion en client) ;
- gestion du **dossier** de souscription : documents KYC, mandat de représentation (signature électronique Yousign), démarches administratives (résiliation/portabilité envoyées en LRE), timeline orange→vert, notification au conseiller à chaque signature ;
- **souscription assistée** : pré-remplissage automatique (Playwright) du formulaire réel de l'opérateur (Free/Bouygues) avec les données du client — jamais de soumission automatique ;
- facturation des honoraires du cabinet (mandat d'honoraires, % de l'économie trouvée) ;
- veille automatique des prix fournisseurs (alerte si une offre moins chère apparaît) et catalogue d'offres auto-alimenté (découverte LLM, validation admin) ;
- **portail self-service** (`frontend-portail`) pour que le client final dépose ses documents, réponde sur sa situation actuelle, fasse son test de débit et suive son dossier sans compte, via un lien à token ;
- **tunnel public de capture de leads** (`/economiser`) avec estimation d'économie calibrée, détection FAI par IP, vérification téléphone, captcha invisible, et dashboard d'attribution par campagne (UTM) ;
- **IA Conseil** : un second parcours de diagnostic ("trame adaptative"), plus riche, avec copilote conseiller en temps réel, anti-biais, cross-sell, PDF de synthèse, agent de veille marché autonome — voir §4.

## 2. Les générations qui coexistent

| Génération | Dossier | Stack | Rôle | Statut |
|---|---|---|---|---|
| **1. Legacy** | `src/` | Streamlit + SQLite (WAL) | Application complète historique | **En cours d'extinction** (voir `GUIDE_LANCEMENT.md`) — encore fonctionnelle, mais plus le développement actif |
| **2. Backend cible** | `backend/` | FastAPI + Postgres (async SQLAlchemy) + Celery/Redis | API métier unique, découplée : dossiers, mandats, signature électronique, LRE, stockage S3, IA Conseil, landing publique | **Actif** — la quasi-totalité des fonctionnalités legacy y est portée, plus des fonctionnalités qui n'existaient que côté backend (IA Conseil, landing `/economiser`, dashboard UTM) |
| **3. Frontends Next.js** | `frontend-conseiller/`, `frontend-portail/` | Next.js 14 | Interfaces qui consomment `backend/` | **`frontend-portail`** : livré et fonctionnel. **`frontend-conseiller`** : application complète (dashboard, prospects, clients, dossiers, diagnostic, facturation, admin, module IA Conseil) — plus un squelette, voir §5 |

Le produit vivait dans `src/` (Streamlit) ; le projet a depuis largement basculé sur `backend/` + `frontend-conseiller/` + `frontend-portail/`. `src/` reste documenté ci-dessous car du code y est encore porté ponctuellement vers le backend (dernier exemple en date : `src/souscription_engine.py` → `backend/services/souscription_engine.py`, le 02/09/2026).

`src/app.py` (Streamlit) parle à **deux APIs** via `src/api_client.py` : `crm_api.py` (SQLite, port 8003, API interne historique) et `backend/main.py` (Postgres, port 8000, nouveau backend), avec un disjoncteur (`_ApiIndisponible`) qui retombe sur un accès direct SQLite si une API ne répond pas.

## 3. Backend cible — `backend/` (FastAPI + Postgres)

`backend/main.py` : `FastAPI(title="IA Conseil — API")`, Sentry si configuré, CORS restreint au portail client + `localhost:3000`, aucune création de table auto (schéma géré uniquement par Alembic), endpoint `/health`.

### Routers (`backend/routers/`)

| Router | Ressource | Auth |
|---|---|---|
| `auth.py` | login, refresh, mot de passe oublié/reset, `/me` | public (login) puis JWT |
| `clients.py` | CRUD clients + briefing | JWT |
| `prospects.py` | CRUD prospects + documents | JWT |
| `dossiers.py` | CRUD dossier, transitions d'état, timeline, notes, offre visée, lien client, PDF restitution, **pré-remplissage souscription** | JWT |
| `mandats.py` | mandat de représentation : génération PDF (brouillon), envoi en signature Yousign, validation, marquage manuel | JWT |
| `honoraires.py` | mandat d'honoraires (rémunération du cabinet), distinct du mandat de représentation | JWT |
| `factures.py` | analyse de facture uploadée (LLM) | JWT |
| `demarches.py` | démarches administratives (génération, envoi LRE, remplissage) | JWT |
| `comparaisons_offres.py` | enregistrements historiques de comparaison d'offres | JWT |
| `offres.py` | `/offres/comparer`, `/offres/recommandations` | JWT |
| `catalogue.py` | pipeline de découverte d'offres (staging → validation admin) | JWT admin |
| `veille.py` | sources de veille prix, historique, alertes, déclenchement manuel | JWT admin |
| `alertes_offres.py` | valider/rejeter une alerte d'offre moins chère | JWT |
| `audit_agent.py` | agent d'audit Claude (tool-use), synthèse chiffrée et sourcée | JWT |
| `parametres.py` | réglages clé/valeur (société, SMTP, Telegram, clés API, logo) | JWT admin |
| `users.py` | CRUD comptes conseillers/admins | JWT admin |
| `admin.py` | actions d'administration transverses | JWT admin |
| `notifications.py` | alertes in-app du conseiller connecté | JWT |
| `dashboard.py` | vue agrégée page d'accueil (relances, KPIs) | JWT |
| `dashboard_utm.py` | tunnel de conversion par campagne, attribution UTM | JWT |
| `geo.py` | auto-complétion ville à partir d'un code postal | JWT |
| `ia_conseil_clients.py`, `ia_conseil_sessions.py`, `ia_conseil_catalogue.py`, `ia_conseil_dashboard.py`, `ia_conseil_souscriptions.py` | module IA Conseil — voir §4 | JWT |
| `leads_public.py` | capture de lead sur la landing `/economiser` | public (rate-limited, captcha) |
| `portail_public.py` | contexte dossier, upload doc, situation actuelle, démarches, speedtest, suivi — **par token, sans compte** | public |
| `speedtest_backend.py` | backend du test de débit (garbage/empty/upload/getIP) | public |
| `stockage_local.py` | sert les fichiers du repli disque local de secours | protégé par token de fichier |
| `webhooks.py` | webhook Yousign (signature électronique) | public (HMAC vérifié) |

### Modèles (`backend/models/`)

**Cœur métier** : `User`, `Client`, `Prospect`, `Dossier`, `Contrat`, `Demarche`, `Document`, `DocumentProspect`, `Mandat` (représentation), `MandatHonoraires`, `Commission`, `HistoriqueAction`.
**Catalogue & veille** : `Offre`, `OffreStaging`, `CatalogueSource`, `ComparaisonOffre`, `AlerteOffre`, `Veille` (sources/historique/alertes).
**Divers** : `Abonnement`, `FactureAnalyse`, `Parametre`, `TokenPublic`, `LoginTentative`, `Notification`, `CampagneCout`, `Touchpoint` (attribution UTM).
**IA Conseil** (préfixe distinct, table `client` séparée de `clients`) : `Categorie`, `Fournisseur`, `OffreConseil`, `TrameTemplate`, `RegleRecommandation`, `ClientConseil`, `SessionTrame`, `Recommandation`, `Souscription`, `AlerteOverride`, `EvenementPlanifie`, `SessionFacture`, `RapportVeilleMarche`.

`Client` et `Prospect` (cœur métier) restent documentés comme des miroirs des tables SQLite historiques (`src/db.py`).

### Logiques métier clés (`backend/services/`)

- **`dossier_engine.py`** — machine à états stricte du parcours de souscription :
  `initie → docs_demandes → docs_recus → mandat_a_signer → mandat_signe → soumis_fournisseur → en_activation → actif → facture`, états terminaux `echec`/`annule`. Construit aussi la **timeline** (orange "en_cours" → vert "termine") affichée au conseiller, pilotée par des signaux métier indépendants du statut brut (ex. l'étape "Mandat signé" passe verte dès que `Mandat.statut == "signe"`, pas seulement quand le dossier a formellement transité).
- **`mandat_engine.py`** — cycle du mandat de représentation en deux temps : `generer_mandat` produit le PDF (statut `brouillon`, pas encore envoyé) pour que le conseiller le relise, puis `envoyer_mandat_en_signature` déclenche l'envoi Yousign (tâche Celery). `traiter_mandat_signe` (déclenché par le webhook Yousign ou par un marquage manuel) fait avancer le dossier, finalise la conversion prospect→client si les documents KYC sont validés, notifie le conseiller (`notification_engine.creer_notification_conseiller`) et programme une relance de suivi.
- **`souscription_engine.py`** — souscription assistée par navigateur Playwright visible, pré-rempli avec les coordonnées du client (Free/Bouygues) ; automatise en plus, chez Free, la cascade d'éligibilité par adresse et le choix de la box correspondant à l'offre catalogue. Ne soumet jamais la commande. Portage 02/09/2026 de `src/souscription_engine.py` (app Streamlit legacy). **Ne fonctionne que si ce backend tourne en local** (le navigateur s'ouvre sur l'écran du process qui l'a lancé) — pas depuis un déploiement distant (Fly.io...), même limite que documentée pour la version Streamlit dans `DEPLOIEMENT.md`.
- **`notification_engine.py`** — email réel (Resend) et SMS (OVH/Twilio) pour le client, plus les notifications in-app du conseiller ; repli silencieux si non configuré.
- **`storage_engine.py`** — stockage documentaire S3-compatible (Scaleway), chiffrement SSE-S3, URLs signées, clés non devinables, fallback disque local en dev.
- **`token_engine.py`** — tokens de lien client public (`secrets.token_urlsafe(32)`, expiration, verrouillage IP optionnel, révocation).
- **`audit_engine.py`** — journal d'audit générique insert-only (`HistoriqueAction`), utilisé par le scoring et la conversion de prospect, et par les actions qui méritent une trace (ex. pré-remplissage de souscription).
- Autres : `alertes_offres_engine.py`, `demarches_engine.py`, `dossier_notifications.py` (templates email/SMS par statut de dossier), `facture_analyzer.py`, `kyc_engine.py`, `lre_engine.py` (AR24), `offres_engine.py`, `restitution_pdf_engine.py`, `document_engine.py` (génération PDF des mandats/démarches), `signature_engine.py` (wrapper Yousign v3), `catalogue_engine.py`, `veille_engine.py`, `prospect_conversion.py`, `prospect_scoring.py`, `relance_engine.py`, `churn_engine.py`, `client_suppression.py`, `reference_engine.py`, `purge_test_data.py`, `eligibilite_fibre.py` / `geo_ip.py` / `telephone_verification.py` / `captcha.py` / `estimation_publique.py` (landing `/economiser`).

### Traitements asynchrones (`backend/workers/tasks.py`, Celery)

`valider_document_kyc`, `envoyer_mandat_signature` / `telecharger_mandat_signe` (Yousign), `relancer_dossiers_stagnants`, `generer_document_demarche`, `envoyer_demarche_lre` / `verifier_accuses_lre_en_attente`, `lancer_veille_periodique`, `detecter_offres_moins_cheres_periodique`, `envoyer_digest_quotidien`. Chaque tâche encapsule son code async via `asyncio.run` (un worker Celery n'a pas de boucle événementielle propre).

### Sécurité (`backend/core/security.py`)

JWT (PyJWT, HS256), hash de mot de passe PBKDF2-SHA256 (260k itérations), types de tokens `access`/`refresh`/`reset`, dépendances FastAPI `get_current_user` / `require_role(*roles)`, limitation des tentatives de connexion (5 essais / 15 min).

### Infra locale (`docker-compose.yml` racine)

Services : `redis`, `postgres` (profil optionnel, sinon Neon en cloud), `backend` (uvicorn --reload, :8000), `celery-worker`, `celery-beat`, `flower` (:5555), `streamlit` (:8501, legacy).

## 4. Module IA Conseil — second parcours de diagnostic

Sous-système parallèle au diagnostic historique, avec sa propre table `client` (modèle `ClientConseil`, pontée au `Client` du cœur métier via `ia_conseil_bridge.py`, créée à la demande à l'entrée du diagnostic fusionné). Persistance et services dédiés : `ia_conseil_engine.py` (orchestration), `ia_conseil_ws.py` (pub/sub Redis pour la mise à jour temps réel des sessions), `ia_conseil_pdf.py` (synthèse PDF de fin de trame), `ia_conseil_facture.py` (upload de facture pendant une session), `ia_conseil_catalogue_sync.py` (synchro planifiée du catalogue), `copilot_engine.py` (copilote conseiller en temps réel), `anti_biais_engine.py` (garde-fou sur le modèle économique), `cross_sell_engine.py`, `veille_marche_agent.py` (agent Claude autonome), `veille_souscriptions_engine.py`, `evenement_planifie_engine.py`.

Côté `frontend-conseiller`, le module vit sous `app/(conseiller)/ia-conseil/` : liste clients, fiche client, session de "trame" adaptative (`clients/[id]/trame/[sessionId]`), dashboard dédié, admin catalogue/veille-marché. Une page de partage public existe aussi hors du groupe authentifié : `app/ia-conseil-partage/[sessionId]/`.

## 5. Frontends Next.js

### `frontend-portail/` — portail client (livré)

Accès **sans compte**, par lien à token (`/dossier/[token]`) : contexte du dossier, économie annuelle estimée, checklist de documents à fournir, sous-pages `documents/`, `demarches/`, `situation/` (situation actuelle mobile/box), `speedtest/`, `suivi/`. Appelle directement `backend/routers/portail_public.py` en `fetch` côté client (`lib/api.ts`), pas de BFF car pas d'authentification à protéger — la sécurité repose sur le token non devinable.

Comprend aussi le **tunnel public de capture de leads** : `app/economiser/` (landing + méthodologie), `app/mentions-legales/`, `app/politique-confidentialite/` — alimente `leads_public.py`, `estimation_publique.py`, `eligibilite_fibre.py`, `geo_ip.py`, `telephone_verification.py`, `captcha.py` côté backend, et le dashboard UTM côté conseiller.

### `frontend-conseiller/` — outil conseiller (application complète)

Interface interne authentifiée qui remplace Streamlit pour les conseillers. Structure de `app/(conseiller)/` :

- `dashboard/` (+ `dashboard/utm/` — attribution de campagnes)
- `diagnostic/` — wizard 4 étapes (univers → identité → situation → recommandations), composants dans `components/diagnostic/`
- `prospects/`, `prospects/[id]/`
- `clients/`, `clients/[id]/`
- `dossiers/`, `dossiers/[id]/` — timeline, offre visée, mandat de représentation (génération/preview/envoi Yousign/validation), mandat d'honoraires, documents KYC, démarches, notes, **pré-remplissage de souscription**
- `facturation/`
- `admin/` (+ `admin/utilisateurs/`, `admin/parametres/`, `admin/catalogue/`, `admin/veille/`, `admin/ocr-facture/`, `admin/donnees-test/`) — réservé au rôle Admin
- `ia-conseil/` — voir §4

**Le proxy BFF** : le navigateur ne parle jamais directement au backend FastAPI. Toutes les requêtes passent par `app/api/backend/[...path]/route.ts`, qui lit les cookies `access_token`/`refresh_token` (HttpOnly), rajoute `Authorization: Bearer`, et relaie vers `BACKEND_URL`. Le backend n'a donc jamais besoin d'autoriser le navigateur en CORS, et le token n'est jamais exposé côté client (pas de faille XSS possible sur le JWT). Auth : `app/api/auth/{login,logout,refresh}/route.ts`, `lib/server/backend.ts`, `contexts/AuthContext.tsx`, `middleware.ts` (garde d'ergonomie ; c'est toujours le backend qui revalide le rôle sur chaque endpoint).

Voir `frontend-conseiller/FRONTEND_CONSEILLER.md` pour le détail technique — **cette page date du socle initial et sous-estime largement ce qui est construit depuis** ; se fier à l'arborescence de `app/(conseiller)/` ci-dessus pour l'état réel.

## 6. Flux de données — vue d'ensemble

```
                     ┌───────────────────────────┐
                     │   Conseiller (interne)     │
                     └─────────────┬─────────────┘
                                   │
        ┌──────────────────────┐  │  ┌──────────────────────────┐
        │  src/app.py           │  │  │ frontend-conseiller/       │
        │  (Streamlit, legacy,  │  │  │ (Next.js, app complète)    │
        │  en cours d'extinction)│  │  └──────────────┬─────────────┘
        └──────┬─────────┬─────┘  │                   │ BFF (cookies HttpOnly)
               │         │        │                    │
        ┌──────▼───┐ ┌───▼────────▼───┐               │
        │crm_api.py│ │ backend/main.py│◄──────────────┘
        │ SQLite   │ │ FastAPI+Postgres│
        │ :8003    │ │ :8000           │
        └──────────┘ └───────┬─────────┘
                              │
                     ┌────────┴────────┐
                     │ Celery + Redis   │  (relances, veille, LRE, signature)
                     └─────────────────┘
                              │
                ┌─────────────┼──────────────┐
                │                             │
       ┌────────▼────────┐          ┌─────────▼─────────┐
       │  frontend-portail│          │  Souscription      │
       │  (client final,  │          │  assistée           │
       │  sans compte,    │          │  (Playwright local, │
       │  via token) +     │          │  Free/Bouygues)     │
       │  landing /economiser         └────────────────────┘
       └──────────────────┘
```

## 7. Structure du dossier (racine du repo)

```
cmr_integral_pro/
├── backend/                    # API cible — FastAPI + Postgres (async SQLAlchemy) + Celery
│   ├── main.py                 # point d'entrée FastAPI
│   ├── core/                   # config, database, security (JWT), logging, rate_limit
│   ├── routers/                # endpoints HTTP — voir tableau §3
│   ├── services/                # logique métier (*_engine.py) — voir §3
│   ├── models/                  # tables SQLAlchemy — voir §3
│   ├── schemas/                 # schémas Pydantic (in/out des routers)
│   ├── workers/                 # tasks.py (Celery), celery_app.py
│   ├── alembic/                  # migrations de schéma (seule source de vérité du schéma)
│   ├── scripts/                  # seed_admin, seed_catalogue, migration SQLite→Postgres, etc.
│   ├── prompts/                  # prompts LLM (analyse facture, KYC, audit agent...)
│   ├── rules_engine/              # règles de recommandation IA Conseil
│   ├── tests/                     # pytest — ~460 tests
│   └── _local_storage/             # repli disque local du stockage documentaire (dev)
│
├── frontend-conseiller/         # outil interne conseiller — Next.js 14, app complète
│   ├── app/(conseiller)/         # pages authentifiées — voir arborescence §5
│   ├── app/ia-conseil-partage/     # page de partage public d'une trame IA Conseil
│   ├── app/api/backend/            # proxy BFF vers backend/ (cookies HttpOnly → Authorization Bearer)
│   ├── app/api/auth/                # login/logout/refresh (pose les cookies)
│   ├── components/                  # diagnostic/, clients/, prospects/, ia-conseil/, admin/, wizard/, ui/ (shadcn)
│   ├── lib/hooks/                    # hooks React Query par domaine (useDossiers, useMandat, useClients...)
│   └── e2e/                          # tests Playwright end-to-end
│
├── frontend-portail/             # portail client final — Next.js 14, sans compte
│   ├── app/dossier/[token]/        # contexte dossier, documents, démarches, situation, speedtest, suivi
│   ├── app/economiser/              # landing publique de capture de leads
│   └── lib/api.ts                    # appels directs au backend (pas de BFF, sécurité par token)
│
├── src/                            # application legacy — Streamlit + SQLite, en cours d'extinction
│   ├── app.py                       # interface unique, pilotée par menu
│   ├── *_engine.py                   # modules métier (offres, prospects, clients, souscription...)
│   ├── db.py                          # SQLite WAL, FTS5, journal d'audit
│   ├── crm_api.py                      # API REST JWT interne (port 8003)
│   └── chatbot_api.py                   # process FastAPI séparé (port 8001), chatbot public de qualification de lead
│
├── docs/                            # documentation (ce fichier, ARCHITECTURE.md, DATABASE.md, API.md...)
├── old/                              # archives — code antérieur non maintenu
├── scripts/, tools/                   # utilitaires ponctuels (audit eval, redis local)
├── docker-compose.yml                  # environnement de dev complet (redis, postgres, backend, celery, streamlit)
├── alembic.ini                          # config des migrations (schéma géré uniquement ici)
├── GUIDE_LANCEMENT.md                     # comment lancer chaque service en local (Windows/Linux)
├── DEPLOIEMENT.md                          # déploiement Fly.io (backend), Vercel (frontends), Neon (Postgres), Upstash (Redis), Scaleway (S3)
└── CLES_API_A_CONFIGURER.md                 # inventaire des clés API/services externes nécessaires
```

## 8. Lancer l'application en local

Voir `GUIDE_LANCEMENT.md` pour le détail complet (Windows via `lancer-app.ps1`, ou Linux). En résumé, les services à démarrer :

```
redis                          # broker Celery
backend      → uvicorn :8000   # API FastAPI
celery-worker / celery-beat    # tâches asynchrones (mandat, LRE, veille, relances)
frontend-conseiller → :3001    # outil conseiller (npm run dev)
frontend-portail     → :3000   # portail client (npm run dev)
streamlit            → :8501   # legacy, en cours d'extinction
```

La **souscription assistée** (`backend/services/souscription_engine.py`) et la **veille prix**/**catalogue** (Playwright) nécessitent que `backend` tourne sur cette même machine locale, navigateur Chromium installé (`playwright install chromium`) — inutilisables depuis un déploiement distant.

## 9. Pour aller plus loin

- Détail technique legacy Streamlit : `docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/API.md`, `IA.CONSEIL.MD`, `IA_CONSEIL_UTILISATION.md`.
- Roadmap produit : `IA_CONSEIL_ROADMAP.md`, `ROADMAP_EXECUTION.md`, `PLAN_IMPLEMENTATION_4_PHASES.md`.
- Bascule Streamlit → frontend conseiller : `frontend-conseiller/FRONTEND_CONSEILLER.md` (à prendre avec recul, voir §5) et `docs/MIGRATION_STREAMLIT_VERS_FRONTEND_CONSEILLER.md`.
- Déploiement et clés API externes : `DEPLOIEMENT.md`, `CLES_API_A_CONFIGURER.md`.
