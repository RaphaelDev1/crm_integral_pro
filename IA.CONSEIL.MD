# IA Conseil — CRM Intégral Pro
## Documentation technique complète

**Mise à jour :** 24/07/2026 — **industrialisation & robustesse** (Chantier 4) : conteneurisation
Docker des 3 process (`backend/Dockerfile`, `src/Dockerfile`, `frontend-portail/Dockerfile`) +
`docker-compose.yml` de dev (backend, Streamlit, Redis, Celery worker/beat, Flower, Postgres local
optionnel), logging structuré JSON (`backend/core/logging.py`), **Sentry** sur les 3 process
(backend, Streamlit, portail Next.js via `@sentry/nextjs`), CSP resserrée sur le portail, garde
d'idempotence sur les tâches Celery d'envoi (mandat Yousign, LRE — une tâche rejouée ne double plus
un envoi), CI GitHub Actions étendue (lint `ruff` sur `backend/`, tests `backend/tests/` désormais
exécutés en CI — ils ne l'étaient pas jusqu'ici —, build Docker des 3 images) et procédure de
déploiement documentée dans `DEPLOIEMENT.md` (Fly.io, Vercel, Neon, Upstash — voir §「Industrialisation
& déploiement」). Et, précédemment : ajout de la **génération automatique des démarches** (`backend/services/demarches_engine.py`, `document_engine.py`, `lre_engine.py`, table `demarches`, routeur `backend/routers/demarches.py`) : génération PDF (mandat, résiliation, portabilité, changement de fournisseur, souscription) puis envoi tracé par **LRE (AR24)**, refusée tant que le mandat de représentation du client n'est pas signé (règle légale) — bloc conseiller « 📮 Démarches » dans `src/app.py` et collecte des champs manquants (RIO, PDL/PCE, RIB) sur le portail client Next.js (`/dossier/[token]/demarches`). Reflète également l'état réel du code des sessions précédentes, y compris la session de travail du 20-23/07 (non encore committée) et l'ajout du **catalogue auto-alimenté** (`catalogue_engine.py`, ingestion LLM de nouvelles offres via `offres_staging`, distinct de la veille prix) et de l'**agent d'audit autonome** (`audit_agent.py`, boucle tool-use qui produit une recommandation chiffrée et sourcée sans jamais laisser le LLM calculer un montant, branché en panneau additif à l'étape 4 du wizard) : l'app Streamlit historique (`src/`, facturation, souscription assistée — dont l'automatisation quasi complète du test d'éligibilité **Free** —, notifications par email **et SMS**, OCR Vision, tests, CI, veille prix automatique, catalogue auto-alimenté, agent d'audit autonome, API REST interne JWT désormais sur le port **8003**, sécurisation Sprint 1 complète : secrets en `.env`, rate limiting login réellement implémenté en base, mot de passe admin aléatoire + changement forcé au premier login) **et** un **pont Streamlit → backend** (`api_client.py`/`app.py` : création de dossier, envoi du lien portail client par SMS/email, mandat d'honoraires, analyse de facture par un second LLM — le tout directement depuis les fiches prospect/client, sans quitter Streamlit) **et** un **suivi de dossier 100% local** (contrats rattachés à un prospect, conversion automatique en client une fois le dossier signé) **et** un **lien à usage personnel** envoyé au prospect pour qu'il transmette lui-même sa facture et son test de débit (table `tokens_prospects`, mini-page publique servie par `chatbot_api.py`) **et** le backend FastAPI/Postgres/Celery (`backend/`, Sprints 2/4/5/6 — voir §「Backend FastAPI + Postgres」) **et** le portail client Next.js (`frontend-portail/`, Sprint 3 — voir §「Portail client」), Postgres Neon réellement provisionné et migré. Pour les commandes détaillées, voir `IA_CONSEIL_UTILISATION.md`. Pour l'état d'avancement sprint par sprint et les tâches restantes, voir `ROADMAP_EXECUTION.md` et `SETUP_STATUS.md`.

---

## 🧩 Prompt explicite — ce que propose l'application aujourd'hui

> IA Conseil est un CRM interne pour conseillers en économies Télécom / Énergie / Abonnements. Un conseiller fait passer un **diagnostic guidé en 4-5 étapes** à un prospect (import automatique de facture PDF/photo par OCR — regex, IA Vision Claude, ou un second LLM dédié —, et de speedtest PDF ou capture d'écran) ; les champs clés (opérateur actuel, satisfaction réseau) sont **rendus obligatoires** (sentinelle "à sélectionner" plutôt qu'une valeur par défaut faussement remplie), avec une barre de progression. L'app **compare la situation actuelle au catalogue d'offres** et calcule l'économie annuelle réalisable, univers par univers (Télécom, Énergie, Abonnements) — le calcul de l'économie sur une offre cross-sell (ex. Box proposée à un prospect Mobile) s'appuie sur un contrat de référence connu du prospect plutôt que sur un coût qui n'a rien à voir —, avec une suggestion d'opérateur local basée sur la satisfaction réseau et le débit mesurés par les autres clients de la même ville. Le client obtient un **PDF/email "aperçu"** (économie totale chiffrée, sans le détail des offres) ; le détail complet (offres nommées, comparatif) ne se débloque qu'après un **devis d'honoraires signé et payé** (mandat de représentation en PDF, suivi de statut Devis envoyé → Payé → Démarches en cours → Terminé), modèle économique basé sur un pourcentage de l'économie trouvée. Une fois l'offre retenue, le prospect peut être suivi comme un **dossier local** (Documents reçus → Mandat envoyé → Mandat signé → Souscription en cours → Actif), avec **conversion automatique en client** dès que ce dossier passe "Actif" ; le conseiller peut aussi **ouvrir un dossier côté backend** (Postgres), envoyer au client le lien de son portail personnel par SMS/email, suivre son avancement, gérer le mandat d'honoraires et faire analyser une facture par un second moteur LLM, sans quitter Streamlit. Le prospect peut également recevoir un **lien à usage personnel** (SMS et/ou email) pour transmettre lui-même sa facture et un test de débit, sans que le conseiller ait à les redemander par téléphone. Pour la souscription, le conseiller peut **ouvrir le lien de souscription affilié en un clic**, ou pour Free/Bouygues **lancer un navigateur pré-rempli automatiquement** (Playwright) — chez Free, le test d'éligibilité par adresse et le choix de la box correspondant à l'offre du catalogue sont automatisés — jamais de soumission automatique de la commande, validation humaine obligatoire. Le prospect converti devient un **client avec contrats** (dont date de fin d'engagement), suivi par relances programmées (recalcul de score de priorité — détaillable ligne par ligne au conseiller —, historique d'audit complet, relance automatiquement calée 14 jours avant la fin d'un engagement en cours), avec alerte automatique au client 60 jours avant l'échéance d'engagement. Un **script indépendant planifiable** (`notifications.py`, cron/tâche planifiée) envoie chaque matin par email et/ou Telegram la liste des relances du jour et des retards, plus un résumé hebdomadaire optionnel — sans dépendre de l'app Streamlit ouverte. Un second script planifiable (`veille_prix_engine.py`) surveille les pages tarifs des opérateurs (Playwright headless) et crée une alerte de changement de prix à valider par un admin avant répercussion au catalogue. Un troisième script planifiable (`catalogue_engine.py`) **découvre** de nouvelles offres à partir de pages tarifs/flux (extraction structurée par LLM, jamais de prix inventé), les dédoublonne et les dépose dans une table de staging validée par un admin avant d'entrer au catalogue. Un **agent d'audit autonome** (`audit_agent.py`, boucle Claude tool-use) peut aussi être lancé depuis l'étape 4 du diagnostic pour orchestrer en un seul appel la comparaison d'offres, la vérification de la base de comparaison cross-sell et la couverture réseau locale, et produire une synthèse chiffrée et sourcée — le LLM ne calcule jamais lui-même un montant, il choisit les outils à appeler et rédige l'explication ; purement indicatif, il ne modifie rien au parcours manuel du conseiller. Une **API FastAPI interne protégée par JWT** (`crm_api.py`) expose tout le CRUD (prospects/clients/contrats/offres) et le diagnostic pour de futures intégrations (mobile, portail client, webhooks) ; Streamlit l'appelle déjà via `api_client.py`, avec repli automatique et transparent sur un accès direct à la base si l'API n'est pas démarrée. L'app gère aussi les **utilisateurs et rôles** (Admin / Conseiller / Lecture), un **tableau de bord** (KPIs, relances groupées par urgence, échéances de contrats à 90 jours, performance par conseiller en vue Admin), la **recherche plein texte** (SQLite FTS5) sur prospects et clients, l'**export Excel**, et une **suite de tests automatisés** (pytest) exécutée en CI (GitHub Actions) à chaque push.

---

## 🎯 Pourquoi ce logiciel ?

Application interne pour conseillers **Télécom / Énergie / Abonnements** : diagnostic client guidé, comparaison d'offres, restitution "aperçu" puis complète après règlement d'honoraires, souscription assistée, suivi des prospects et clients jusqu'à la conversion en contrats signés — avec relances automatisées même app fermée.

---

## 🏗️ Stack technique

- **Backend / UI** : Python + Streamlit (une seule app multi-pages pilotée par un menu latéral)
- **Base de données** : SQLite en mode WAL (écritures concurrentes sécurisées), `PRAGMA foreign_keys=ON`, index **FTS5** pour la recherche plein texte
- **Auth** : PBKDF2-HMAC-SHA256 (260 000 itérations), comptage nominatif, 3 rôles, rate limiting login réellement implémenté (table `login_tentatives`, 5 échecs/15 min par identifiant+IP), mot de passe admin généré aléatoirement au premier lancement + changement forcé (`utilisateurs.doit_changer_mdp`) au premier login
- **Secrets** : priorité aux variables d'environnement (`.env`, `src/secrets_config.py` — SMTP, clé Anthropic, Telegram, SMS OVH/Twilio, `CRM_API_SECRET`), repli sur l'ancien stockage en base tant qu'une variable n'est pas définie
- **PDF** : lecture (PyPDF2 — factures/speedtest, texte embarqué) + lecture IA (API **Anthropic Claude Vision**, photo/scan/PDF image, facture **et** speedtest) + génération (fpdf2 — aperçu régénérable à la volée pour un prospect, restitution complète, devis, mandat)
- **Email** : SMTP (smtplib), gabarits HTML inline
- **SMS** : `sms_engine.py` — OVH (API signée, par défaut) ou Twilio, mêmes variables d'environnement que `backend/.env.example`, repli silencieux (email seul / lien à copier) si non configuré
- **Souscription assistée** : Playwright (navigateur visible, process détaché) — pré-remplissage des coordonnées, **et chez Free** automatisation du test d'éligibilité par adresse (cascade code postal → ville → voie → numéro) et du choix de la box correspondant à l'offre du catalogue ; ne soumet jamais la commande elle-même
- **Notifications planifiées** : script Python autonome (cron / tâche planifiée Windows), email + Telegram + SMS (lien documents prospect)
- **Veille prix** : Playwright headless (scraping planifiable) + tables `sources_veille`/`veille_historique_prix`/`veille_alertes`, validation admin avant impact catalogue
- **Catalogue auto-alimenté** : `requests` (+ repli Playwright headless) et extraction LLM structurée (Claude, tool-use) pour découvrir de nouvelles offres + tables `catalogue_sources`/`offres_staging`, dédoublonnage par hash de contenu, validation admin avant impact catalogue
- **API REST interne** : FastAPI (`crm_api.py`, port **8003**), auth **JWT** (PyJWT, `jwt_auth.py`), process indépendant de Streamlit, consommée par Streamlit via `api_client.py` (repli auto sur accès direct BDD)
- **Pont vers le backend** : `api_client.py` appelle aussi `backend/main.py` (port 8000, `BACKEND_API_URL`) pour les dossiers, mandats d'honoraires et l'analyse de facture LLM — sans repli local possible (voir §「Backend FastAPI + Postgres」)
- **API chatbot publique** : FastAPI (`chatbot_api.py`), sans auth, dédiée au widget de site **et** à la mini-page publique où un prospect transmet lui-même sa facture/son test de débit via un lien personnel
- **Export** : Excel (openpyxl)
- **Tests** : pytest, suite dans `src/tests/`, CI GitHub Actions (`.github/workflows/tests.yml`) sur chaque push/PR

Dépendances (`src/requirements.txt`) : `streamlit`, `pandas`, `PyPDF2`, `fpdf2`, `openpyxl`, `anthropic`, `playwright`, `fastapi`, `uvicorn`, `pyjwt`, `requests`, `beautifulsoup4` (parsing HTML pour `catalogue_engine.py`), `python-dotenv`, `python-multipart`, `sentry-sdk`.
Dépendances dev (`src/requirements-dev.txt`) : `+ pytest`, `pytest-cov`.

Le nouveau backend (`backend/requirements.txt`) est un projet **séparé** : `fastapi`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pyjwt`, `pydantic`/`pydantic-settings`, `python-dotenv`, `httpx`, `anthropic`, `celery[redis]`, `boto3` (S3), `stripe`, `resend`, `python-multipart` (upload de fichiers), `sentry-sdk`, `flower` (monitoring Celery) — voir section dédiée plus bas. Dépendances dev (`backend/requirements-dev.txt`) : `+ pytest`, `pytest-cov`, `ruff`. Le portail client (`frontend-portail/package.json`) est un projet Node séparé : `next` 14.2.35, `react`/`react-dom` 18, `lucide-react`, `@sentry/nextjs`, Tailwind/TypeScript en devDependencies.

---

## 🗂️ Structure complète du dépôt

Vue d'ensemble avant le détail fichier-par-fichier (donné plus bas, par sous-système) :

```
cmr_integral_pro/
├── src/                        # App Streamlit conseiller + API CRM interne + chatbot public (SQLite)
│   ├── app.py, db.py, auth.py, *_engine.py, api_client.py, crm_api.py, chatbot_api.py, ...
│   ├── static/                 # Widget JS chatbot + mini-page publique portail prospect
│   ├── tests/                  # Suite pytest (194 tests)
│   ├── Dockerfile              # Image Streamlit (+ Playwright/Chromium, contexte = racine repo)
│   └── requirements.txt / requirements-dev.txt
├── backend/                    # API FastAPI + Postgres (Neon) + Celery (Redis) — second système
│   ├── core/                   # config.py (Settings), database.py, security.py, logging.py
│   ├── models/, schemas/, routers/, services/, workers/  # SQLAlchemy, Pydantic, endpoints, métier, Celery
│   ├── alembic/                # Migrations Postgres
│   ├── tests/                  # Suite pytest mockée (82 tests, aucun Postgres réel requis)
│   ├── Dockerfile              # Image backend/Celery (contexte = racine repo)
│   └── requirements.txt / requirements-dev.txt
├── frontend-portail/           # Portail client Next.js (sans login, accès par lien à token)
│   ├── app/, lib/               # Pages App Router + client HTTP typé vers backend/
│   ├── sentry.*.config.ts, instrumentation.ts, instrumentation-client.ts  # Sentry (@sentry/nextjs)
│   ├── Dockerfile / .dockerignore  # Image standalone (contexte = frontend-portail/ lui-même)
│   └── package.json
├── docs/                       # API.md, ARCHITECTURE.md, DATABASE.md, CHANGELOG.md, CONTRIBUTING.md
├── scripts/                    # eval_audit.py (évaluation de l'agent d'audit, cas de test)
├── .github/workflows/          # tests.yml (lint + tests Streamlit + tests backend + build Docker), update-docs.yml
├── docker-compose.yml          # Environnement de dev complet (backend, streamlit, redis, celery, flower)
├── .dockerignore                # Racine (builds backend/streamlit) — voir aussi frontend-portail/.dockerignore
├── pyproject.toml              # Config ruff (lint scopé à backend/)
├── alembic.ini                 # Pointeur vers backend/alembic (config Alembic elle-même dans backend/core/config.py)
├── DEPLOIEMENT.md              # Procédure de déploiement (Fly.io, Vercel, Neon, Upstash) — rien de déployé à ce jour
├── SETUP_STATUS.md             # État des comptes/clés tiers à créer manuellement
├── ROADMAP_EXECUTION.md        # Suivi sprint par sprint
├── IA_CONSEIL_UTILISATION.md   # Commandes détaillées (installation, lancement, tests)
└── IA.CONSEIL.MD               # Ce document — référence technique complète
```

---

## 📁 Organisation du code (`src/`)

| Fichier | Rôle |
|---|---|
| `app.py` | Point d'entrée Streamlit : session, navigation, toutes les pages/UI |
| `db.py` | Connexion SQLite, création du schéma, migrations incrémentales, audit trail (`historique_actions`), table `parametres` (clé/valeur), index FTS5, tables `login_tentatives` et `tokens_prospects` |
| `auth.py` | Hash/vérification mot de passe, CRUD utilisateurs, création admin par défaut (mot de passe aléatoire + changement forcé), rate limiting login (`authentifier_avec_limite`, table `login_tentatives`, 5 échecs/15 min par identifiant+IP) |
| `secrets_config.py` | Point d'accès unique aux secrets : priorité `.env` (SMTP, `ANTHROPIC_API_KEY`, Telegram, SMS OVH/Twilio), repli sur la table `parametres` en base |
| `constants.py` | Listes déroulantes métier (opérateurs, fournisseurs énergie, univers, catégories, rôles, statuts facture…) + listes « obligatoires » avec sentinelle `SENTINEL_NON_RENSEIGNE` pour forcer une réponse explicite du conseiller |
| `utils.py` | Helpers génériques : validation email/tél, parsing date, export Excel, génération de référence, construction de lien affilié, économie totale groupée par catégorie (`economie_totale_groupee`), coût mensuel total tous univers (`cout_total_mensuel`) |
| `prospects_engine.py` | CRUD prospects + widget de relance (`widget_relance`, calé sur la fin d'engagement) + scoring de priorité (`calculer_score_prospect`/`expliquer_score_prospect`) + coût de référence par catégorie pour le cross-sell (`cout_reference_categorie`) + lien personnel documents (`creer_token_documents`/`valider_token_documents`) + recherche FTS5 |
| `clients_engine.py` | CRUD clients + couverture réseau par ville (satisfaction et débit) + widget de relance client + mapping vers le client miroir backend (`definir_backend_client_id`) + recherche FTS5 |
| `contrats_engine.py` | CRUD contrats rattachés à un client **ou à un prospect** (`prospect_id`) — un contrat prospect est soit une référence externe (service déjà souscrit ailleurs, base de comparaison cross-sell), soit un dossier en cours (`type_contrat='dossier_cmr'`, suivi via `ETAPES_CONTRAT`) — + transfert des contrats vers le client à la conversion (`transferer_contrats_dossier_vers_client`) + liste des contrats arrivant à échéance |
| `offres_engine.py` | Catalogue d'offres (avec lien de souscription/affiliation, URLs Free pointant vers le vrai tunnel de souscription) + moteur de comparaison/recommandation |
| `pdf_engine.py` | Extraction facture/speedtest (PyPDF2 regex + Claude Vision, facture **et** speedtest) + génération PDF (aperçu — avec détail des catégories proposées et régénération à la volée pour un prospect via `construire_apercu_pdf_prospect` —, restitution complète, devis, mandat) |
| `facturation_engine.py` | CRUD devis d'honoraires, cycle de statut, signature du mandat, rattachement au client à la conversion |
| `souscription_engine.py` | Pré-remplissage assisté (Playwright) du formulaire de souscription en ligne (Free/Bouygues) ; chez Free, automatise en plus le test d'éligibilité par adresse (cascade CP/ville/voie/numéro) et le choix de la box correspondant à l'offre du catalogue — sans jamais soumettre la commande |
| `email_engine.py` | Envoi SMTP + gabarits HTML (bilan, alerte fin d'engagement) |
| `sms_engine.py` | Envoi de SMS via OVH (API signée, par défaut) ou Twilio, mêmes variables que `backend/.env.example` — repli silencieux (`False`) si non configuré |
| `notifications.py` | Script autonome planifiable : digest quotidien des relances (email/Telegram) + alerte fin d'engagement + résumé hebdo + notification immédiate de nouveau prospect chatbot + envoi du lien documents prospect par SMS/email (`envoyer_demande_documents_prospect`) + alerte conseiller à réception d'un document prospect (`notifier_document_prospect_recu`) |
| `chatbot_engine.py` | Chatbot public : boucle agentique Claude (tool-use) qui collecte progressivement les infos du diagnostic et crée le prospect en fin de conversation |
| `audit_agent.py` | Agent d'audit autonome : boucle agentique Claude (tool-use, même architecture que `chatbot_engine.py`) qui orchestre `comparer_offres`/`cout_reference_categorie`/`couverture_reseau` pour produire une recommandation chiffrée et sourcée en un seul appel — le LLM ne calcule jamais un montant, choisit seulement les outils et rédige l'explication ; appelé depuis le panneau « 🤖 Audit automatique » de l'étape 4 du wizard |
| `chatbot_api.py` | API FastAPI **publique, sans auth** (process indépendant de Streamlit) exposant le chatbot, les endpoints prospects/offres/bilan au widget JS, **et** le portail prospect (`/portail/{token}`, upload facture/speedtest, régénération du PDF aperçu) |
| `static/chatbot_widget.js` | Widget de chat embarquable sur n'importe quel site (aucune dépendance, à charger via `<script src=".../widget/chatbot_widget.js" data-api-url="...">`) |
| `static/portail_prospect.html` | Mini-page publique (HTML/JS statique) où un prospect, via son lien personnel, transmet sa facture et un test de débit — servie par `chatbot_api.py` |
| `crm_api.py` | API FastAPI **interne, protégée par JWT**, port **8003** (process indépendant de Streamlit et distinct de `backend/`) : CRUD complet prospects/clients/contrats/offres + endpoints diagnostic ; doc Swagger sur `/docs` |
| `jwt_auth.py` | Émission/validation des JWT (`creer_token`, `get_current_user`, `require_role`) — secret lu dans `CRM_API_SECRET` (obligatoire si `APP_ENV=production`), jetons compatibles avec `backend/core/security.py` (champ `"type": "access"`) |
| `api_client.py` | Utilisé par `app.py` à la place des modules `*_engine.py` : mêmes signatures, appelle `crm_api.py` (`CRM_API_URL`, port 8003) en HTTP et retombe automatiquement sur l'accès direct à la base si l'API est injoignable ; expose aussi un **pont direct vers `backend/`** (`BACKEND_API_URL`, port 8000, sans repli local) pour les dossiers, mandats d'honoraires et l'analyse de facture LLM |
| `veille_prix_engine.py` | Script planifiable : scrape (Playwright headless) les pages tarifs opérateurs, détecte les changements de prix, crée des alertes `en_attente` validées/rejetées par un admin |
| `catalogue_engine.py` | Script planifiable : **découvre** de nouvelles offres (contrairement à `veille_prix_engine.py`, qui ne fait que suivre le prix d'une offre déjà connue) — récupère une page/un flux (`requests` puis repli Playwright), en extrait les offres via un LLM (Claude, sortie JSON structurée, jamais de prix inventé), les normalise et les dédoublonne (hash de contenu), puis les dépose dans `offres_staging` en attente de validation admin |
| `tests/` | Suite pytest (auth, offres, catalogue, utils, pdf, prospects, contrats, souscription, chatbot, notifications, sms) + `conftest.py` |
| `pytest.ini` | Configuration pytest |
| `ia_conseil_crm.db` | Base SQLite (créée/migrée automatiquement au premier lancement) |

---

## 🗄️ Base de données

```
utilisateurs        id, username, nom_complet, password_hash, role, actif, date_creation,
                     doit_changer_mdp (changement de mot de passe exigé au prochain login)
prospects           id, ref, identité, ville/CP, univers_interesse, situation actuelle
                     (opérateur, techno, data, coût, satisfaction, débits ⬇️⬆️),
                     énergie (fournisseur, coûts), abonnements (JSON), lignes_multi (JSON),
                     economie_estimee_an, notes, statut, date_creation, date_relance,
                     date_fin_engagement (échéance du contrat actuel chez son opérateur),
                     cree_par, offres_interet (JSON — offres cochées "intéresse le client"),
                     score (priorité de relance, recalculée à chaque affichage),
                     backend_client_id (mapping vers le client miroir côté backend/ Postgres)
clients              mêmes champs de situation que prospects, + date_relance, statut_relance
                     ("Aucune" / "À relancer" / "Relancé"), backend_client_id (idem prospects)
contrats             id, client_id (FK, nullable), prospect_id (FK, nullable — l'un des deux est
                     rempli), univers, categorie, fournisseur, nom_offre, cout_mensuel,
                     economie_mensuelle, reference_contrat, statut_contrat, type_contrat
                     (NULL/"reference_externe" = service déjà souscrit ailleurs par le prospect,
                     "dossier_cmr" = dossier en cours de vente avec nous, suivi via ETAPES_CONTRAT),
                     date_souscription, date_fin_engagement, notes, cree_par
offres               catalogue : id, univers, categorie, fournisseur, nom_offre, prix_mensuel,
                     frais_activation, engagement_mois, data_go, caracteristiques,
                     commission_affiliation, url_souscription, code_affiliation, actif, date_maj
factures             devis d'honoraires : id, reference, prospect_id, client_id, identité,
                     economie_annuelle, taux_honoraires, montant_honoraires, statut
                     (Devis envoyé → Payé → Démarches en cours → Terminé), date_creation,
                     date_paiement, mandat_signe, mandat_signataire, mandat_date_signature,
                     notes, cree_par
parametres           clé/valeur générique : config SMTP, nom société, taux d'honoraires par
                     défaut, clé API Anthropic, destinataire notifications, jeton/chat Telegram
historique_actions   audit trail insert-only : entite_type, entite_id, action, details,
                     auteur, date_action
login_tentatives     rate limiting login, insert-only : id, identifiant, ip, succes,
                     date_tentative (fenêtre glissante 15 min, purge opportuniste > 1 jour)
tokens_prospects     lien personnel « transmettre facture + test de débit », sans login :
                     id, prospect_id (FK), token (unique), date_creation, date_expiration
                     (14 jours par défaut), date_derniere_utilisation, nb_utilisations, revoque
sources_veille       page tarif surveillée : id, univers, categorie, fournisseur, nom_offre,
                     offre_id (FK offres, nullable), url, selecteur_prix, actif, dernier_prix,
                     date_derniere_verif, date_creation
veille_historique_prix  relevé de prix insert-only : id, source_id (FK), prix, date_releve
veille_alertes       changement de prix détecté : id, source_id (FK), ancien_prix, nouveau_prix,
                     statut (en_attente / validee / rejetee), date_detection, date_traitement
catalogue_sources    page/flux à ingérer pour découvrir de nouvelles offres (cf.
                     catalogue_engine.py) : id, univers, categorie, fournisseur, url,
                     type_source (page_officielle/flux_partenaire/open_data),
                     methode (requests/playwright), actif, robots_ok, frequence_h,
                     date_derniere_ingestion, date_creation
offres_staging       offre détectée par catalogue_engine.py, jamais écrite directement dans
                     `offres` : id, source_id (FK), mêmes colonnes qu'`offres` + hash_contenu,
                     statut (en_attente / validee / rejetee / doublon / a_verifier),
                     confiance_llm, champs_incertains (JSON), payload_brut (JSON),
                     offre_existante_id (FK offres, nullable — renseigné si le hash correspond
                     à une offre déjà au catalogue dont le prix diffère, cas "changement"),
                     date_detection, date_traitement
```

Index **FTS5** (`prospects`, `clients`) synchronisé automatiquement pour la recherche plein texte (nom, ville, email, opérateur…).

Les migrations (`db._migrer_bdd`) ajoutent automatiquement les colonnes/tables manquantes à chaque démarrage — aucune action manuelle requise en cas de mise à jour du code.

---

## 🔐 Rôles & permissions

| Rôle | Voir | Modifier | Admin |
|---|---|---|---|
| Admin | ✅ | ✅ | ✅ |
| Conseiller | ✅ | ✅ | ❌ |
| Lecture | ✅ | ❌ | ❌ |

Chaque création/modification est tracée (`cree_par` + `historique_actions`). Un conseiller ne voit par défaut que ses propres prospects/clients ; l'Admin peut activer une « vue globale ».

---

## 🚀 Étapes une à une — du lancement à la conversion

### 1. Lancer l'application
```bash
cd src
pip install -r requirements.txt
streamlit run app.py
```
Au tout premier lancement, un compte admin est créé automatiquement : identifiant `admin`, mot de passe **généré aléatoirement et affiché une seule fois** à l'écran de connexion (à noter immédiatement). Le changement de ce mot de passe est **exigé automatiquement** dès la première connexion (écran bloquant). Au-delà de 5 échecs de connexion consécutifs (même identifiant + IP), la connexion est bloquée 15 minutes.

### 2. Se connecter
Panneau latéral gauche → identifiant + mot de passe → **Se connecter**. La sidebar affiche ensuite le menu de navigation (📊 Tableau de bord, 🧭 Nouveau diagnostic, 📇 Prospects, 👥 Clients & contrats, 🧾 Facturation, 🛠️ Admin) et 3 compteurs personnels (mes prospects, à relancer, mes clients).

### 3. Démarrer un diagnostic (menu « 🧭 Nouveau diagnostic »)
Wizard en 4 à 5 étapes :

1. **Besoins + import** : cocher les univers à analyser (Télécom / Énergie / Abonnements), choisir le service télécom recherché, importer en option une facture (PDF, photo ou scan — analysée par IA Vision Claude si une clé API est configurée, sinon extraction PyPDF2 classique par regex, PDF texte uniquement) et/ou un speedtest PDF (pré-remplit les débits).
2. **Coordonnées client** : type (Particulier/Pro), identité, téléphone, email, ville/CP — validation format email/téléphone en temps réel.
3. **Situation actuelle** — les champs clés sont **obligatoires** (opérateur actuel, coût mensuel, satisfaction réseau réelle, data mobile minimum) : tant qu'ils ne sont pas renseignés, une sentinelle « — À sélectionner — » les affiche comme non remplis (plutôt qu'une valeur par défaut faussement "remplie", ex. satisfaction pré-cochée sans avoir réellement posé la question) et une barre de progression indique le pourcentage de champs obligatoires renseignés :
   - *Télécom* : opérateur, technologie, offre/coût actuels, débits mesurés, satisfaction réseau, lignes multi. Si le client n'est pas pleinement satisfait et que la ville est renseignée, deux encarts informatifs apparaissent : le meilleur opérateur local par **satisfaction** déclarée, et le meilleur opérateur local par **débit mesuré** (⬇️/⬆️ Mbps moyens chez les prospects/clients de la même ville).
   - *Énergie* : fournisseur actuel, coûts élec/gaz.
   - *Abonnements* : ajout libre d'abonnements existants (nom + coût).
4. **Recommandations** : un panneau **« 🤖 Audit automatique »** (repliable, en haut de l'étape) permet de lancer l'agent d'audit (`audit_agent.py`) — une synthèse sourcée (situation détectée, offres recommandées + pourquoi + source, économie totale, points d'attention, niveau de confiance, traçabilité des outils appelés) affichée à titre indicatif, sans rien modifier au parcours ci-dessous. Le moteur compare aux offres du catalogue et affiche, par univers, l'offre la mieux classée (toujours incluse) + les alternatives, avec économie annuelle. Chaque offre proposée (Télécom, Énergie, Abonnements) peut être cochée **⭐ Intéresse le client** — ces offres sont reprises dans la fiche prospect et débloqueront la restitution complète après paiement. Pour chaque offre avec lien de souscription, un bouton **🔗 Souscrire** ouvre le lien affilié (avec code d'affiliation + coordonnées client en paramètres), et l'action est tracée. En bas de page — **restitution "aperçu"** (l'économie totale, sans le détail des offres ; le détail se débloque via un devis d'honoraires, menu 🧾 Facturation) :
   - 📄 Télécharger le PDF (aperçu)
   - 📧 Envoyer au client (nécessite un SMTP configuré et un email client)
   - 📇 Enregistrer prospect
   - ✅ Convertir en client (directement, sans passer par prospect)
5. **Confirmation conversion** (si étape 4 → « Convertir en client ») : cocher/ajuster les offres réellement souscrites → création du client + des contrats correspondants.

### 4. Suivre les prospects (menu « 📇 Prospects »)
- Liste filtrable par statut, **recherche plein texte** (FTS5 — nom, ville, email, opérateur…), export Excel.
- Fiche détaillée (essentiel en accès direct — nom/prénom/tél/email/coût total/économie —, détails secondaires dans une popup **🔍 Détails du prospect**, avec le détail du calcul du score de priorité) : coordonnées, situation, offres qui l'intéressaient (avec bouton **🔗 Souscrire**, et un bouton **🖊️ Pré-remplir la souscription** toujours affiché dès qu'un lien de souscription existe — pour Free/Bouygues, ouvre un navigateur avec le formulaire pré-rempli, et chez Free automatise en plus l'éligibilité et le choix de la box —, validation manuelle obligatoire, rien n'est jamais soumis automatiquement), historique.
- **Demander facture + test de débit** : génère un **lien à usage personnel** (14 jours de validité) envoyé au prospect par SMS et/ou email, vers une mini-page publique où il transmet lui-même sa facture et un test de débit (analysés automatiquement, mêmes moteurs regex/Vision que le diagnostic) — le conseiller est notifié (email/Telegram) dès réception, sans avoir eu à les redemander par téléphone.
- **Suivi de dossier** (une fois des offres cochées « intéresse le client ») : sélection des offres réellement retenues → crée un ou plusieurs contrats rattachés au prospect (`type_contrat='dossier_cmr'`), suivis par une progression **Documents reçus → Mandat envoyé → Mandat signé → Souscription en cours → Actif** (bouton étape suivante + correction manuelle/résiliation) — dès que le dossier passe **Actif**, le prospect est **automatiquement converti en client** (contrats migrés, fiche prospect supprimée, action tracée). Distinct du dossier backend ci-dessous : celui-ci ne dépend que de SQLite, sans backend/ à lancer.
- **Dossier côté backend** (optionnel, nécessite `backend/main.py` lancé) : créer un dossier Postgres pour ce prospect, envoyer le lien de son portail client par **SMS ou email**, consulter la timeline/le briefing, gérer le **mandat d'honoraires** (création, marquage signé) et faire analyser une facture par le moteur LLM du backend — directement depuis la fiche, sans quitter Streamlit ; affiche un message clair (pas une erreur bloquante) si le backend n'est pas lancé.
- Tri optionnel par **🔥 score de priorité** (activé par défaut), avec colonnes `priorité`/`score` dans le tableau.
- **Modifier** le prospect (champs clés en un clic « 💾 Enregistrer »).
- **Convertir en client** (manuelle, indépendante du suivi de dossier ci-dessus) : ouvre un écran de sélection des offres cochées « intéresse le client » (case à cocher + prix/économie éditables par offre) avant de créer le client et ses contrats — le prospect est alors supprimé et l'action tracée dans l'historique ; les devis d'honoraires existants du prospect sont rattachés au nouveau client.
- **Relance** : bouton principal « ✅ Relance effectuée » qui reprogramme automatiquement à +7 jours ; option repliée « 📅 Date de fin d'engagement » pour les prospects encore engagés — la relance est alors calée automatiquement 14 jours avant cette échéance plutôt qu'à une date arbitraire. Un prospect nouvellement créé est toujours positionné sur « aujourd'hui » (relance = jour-J).
- Suppression (avec confirmation).

### 5. Suivre le tableau de bord (menu « 📊 Tableau de bord »)
- KPIs : prospects total, à relancer, clients signés, économies générées.
- **Relances prospects à traiter** : groupées Retard / Aujourd'hui / À venir / Sans date, triées par **score de priorité** décroissant dans chaque groupe (🔴 chaud / 🟡 tiède / 🟢 froid), avec action rapide (relancer, convertir, supprimer) sur un prospect sélectionné.
- **Relances clients à traiter** : même logique de groupement, cadence par défaut à +1 mois (le temps d'appeler et faire le point) — un client n'entre dans ce suivi que lorsqu'une relance a été programmée manuellement sur sa fiche.
- **Contrats arrivant à échéance (90 jours)** : liste des contrats dont la date de fin d'engagement tombe dans les 90 prochains jours, triés par urgence, avec envoi manuel de l'email de rappel au client (proposition d'offre alternative si une économie a été identifiée dans le catalogue). Une alerte est aussi envoyée **automatiquement** 60 jours avant l'échéance par le script `notifications.py`.
- Derniers clients enregistrés.
- Vue Admin : bascule « vue globale » (toute l'équipe) + tableau de performance par conseiller.

### 6. Gérer les clients & contrats (menu « 👥 Clients & contrats »)
- Recherche plein texte (FTS5 : nom, ville, email, réf., opérateur…), export Excel.
- Fiche client : coordonnées, situation, statut de relance courant + bouton pour programmer/reprogrammer une relance (par défaut +1 mois, option date précise).
- Modification des informations, liste des contrats (total mensuel / économie mensuelle), ajout/modification/suppression de contrat — dont une **date de fin d'engagement** optionnelle qui alimente le suivi d'échéance (Tableau de bord) et l'alerte automatique, et une progression d'étapes (même widget que le suivi de dossier prospect, correction manuelle/résiliation possible). Pour un contrat Free/Bouygues, un bouton **🖊️ Pré-remplir la souscription** est disponible (automatisation complète de l'éligibilité chez Free).
- **Dossier côté backend** (optionnel, nécessite `backend/main.py` lancé) : mêmes fonctionnalités que côté prospect — créer un dossier Postgres, envoyer le lien du portail client par SMS/email, consulter la timeline/le briefing, gérer le mandat d'honoraires, faire analyser une facture par le moteur LLM du backend.
- Suppression du client (supprime aussi ses contrats — confirmation requise).
- Historique complet des actions sur la fiche.

### 7. Facturation (menu « 🧾 Facturation ») — devis d'honoraires & mandat
Le business model : l'économie totale est annoncée gratuitement (PDF/email "aperçu"), mais le **détail des offres** ne se débloque qu'après ce parcours.

- **Créer un devis** : sélection d'un prospect, économie annuelle (pré-remplie), taux d'honoraires (% de l'économie, valeur par défaut réglable en Admin) → montant calculé automatiquement, devis créé (référence `FAC-...`, statut initial « Devis envoyé »).
- **Fiche devis** : téléchargement du **PDF devis** et du **PDF mandat de représentation**, cycle de statut en un clic (Devis envoyé → Payé → Démarches en cours → Terminé, avec date de paiement fixée automatiquement au premier passage à « Payé »), enregistrement de la **signature du mandat** (nom du signataire + date).
- **Restitution complète (post-paiement)** : une fois le statut « Payé »/« Démarches en cours »/« Terminé » atteint, le **PDF complet** (détail des offres, comparatif) devient téléchargeable, reconstruit depuis les offres d'intérêt du prospect ou les contrats du client.
- Liste filtrable par statut, compteur total.

### 8. Administration (menu « 🛠️ Admin », réservé Admin)
8 onglets :
- **👤 Utilisateurs** : création de comptes, modification (nom/rôle/statut actif/mot de passe), suppression.
- **📚 Catalogue** : 3 sous-onglets — **Catalogue actif** (liste des offres, modification de prix, activation/désactivation, suppression, lien de souscription + code d'affiliation), **Sources à ingérer** (pages/flux à ingérer automatiquement pour découvrir de nouvelles offres — univers/catégorie/URL/méthode requests ou Playwright, bouton « 🔎 Ingérer maintenant » par source), **Offres détectées** (offres en attente issues de l'ingestion automatique, avec distinction nouvelle offre / changement de prix, boutons Valider/Rejeter — cf. `catalogue_engine.py`).
- **➕ Ajouter une offre** : formulaire (dont URL de souscription/code d'affiliation) + lien direct vers un comparateur externe selon l'univers.
- **⚡ Pré-remplir (démo)** : charge un jeu d'offres type pour tester rapidement.
- **📧 Email** : nom de société (en-tête PDF/email), configuration SMTP (serveur, port, identifiant, mot de passe), et **réglages de `notifications.py`** (email du conseiller à notifier, jeton bot + chat ID Telegram) — persistés en base pour être réutilisables par le script planifié.
- **💶 Facturation** : taux d'honoraires par défaut appliqué à la création d'un devis.
- **🔍 OCR Vision** : activation de l'extraction de facture par IA (clé API Anthropic, stockée en base, jamais affichée en clair) — sans clé, l'app retombe automatiquement sur l'extraction PyPDF2 classique.
- **📈 Veille prix** : 3 sous-onglets — **Sources surveillées** (ajout d'une page tarif à surveiller : univers/catégorie/fournisseur/URL/sélecteur CSS, offre du catalogue à mettre à jour après validation, bouton « 🔎 Lancer la veille maintenant »), **Alertes en attente** (valider ou rejeter chaque changement de prix détecté), **Historique des prix** (graphique de tendance par source). Nécessite `playwright install chromium` pour scraper réellement (sinon message d'avertissement).

### 9. API REST interne (menu Admin exclu — `crm_api.py`, process séparé, JWT)

À distinguer de l'API chatbot publique (section 🤖 plus bas) : celle-ci est **authentifiée** et réservée aux intégrations internes/futures (CRUD complet, diagnostic). Streamlit s'y connecte déjà via `api_client.py` mais continue de fonctionner normalement si elle n'est pas lancée (repli silencieux sur la base directe, avec un `st.toast` d'avertissement une fois par session).

```bash
cd src
uvicorn crm_api:app --host 0.0.0.0 --port 8003
```
Port **8003** (et non 8000) : `backend/` (FastAPI + Postgres, section suivante) occupe déjà le port 8000 et n'implémente ni `/contrats` ni `/offres` — les faire cohabiter sur le même port a déjà provoqué des `IntegrityError` et des clients « impossibles à supprimer » (requêtes routées vers la mauvaise base). Ce sont deux projets volontairement isolés.

- `POST /auth/login` (username/password → JWT, 8h de validité, anti-bruteforce identique à Streamlit) puis `Authorization: Bearer <token>` sur toutes les routes suivantes.
- CRUD `GET/POST/PATCH/DELETE` sur `/prospects`, `/clients`, `/clients/{id}/contrats`, `/contrats/{id}` — écriture réservée aux rôles Conseiller/Admin.
- CRUD `/offres` réservé au rôle Admin (comme l'onglet Catalogue).
- Diagnostic authentifié : `POST /diagnostic/comparer`, `/diagnostic/bilan`, `/diagnostic/complet` (multi-univers Télécom + Énergie + Abonnements, pour de futurs clients headless : app mobile, portail client, webhooks).
- `GET /health`, doc Swagger sur `GET /docs`.
- Secret JWT via la variable d'environnement `CRM_API_SECRET` (obligatoire si `APP_ENV=production` — l'API refuse de démarrer sans lui ; sinon secret de dev affiché en avertissement). Jetons compatibles `backend/core/security.py` (champ `"type": "access"`). Côté Streamlit, `CRM_API_URL` (défaut `http://127.0.0.1:8003`) et `CRM_API_TIMEOUT` (défaut 3s) sont configurables par variable d'environnement ; `BACKEND_API_URL` (défaut `http://127.0.0.1:8000`) cible séparément `backend/main.py` pour les dossiers/mandats/facture LLM (aucun repli local possible sur ces fonctions).

### 10. Notifications planifiées (`notifications.py`, hors app Streamlit)
Script autonome à lancer via une tâche planifiée quotidienne, indépendant de Streamlit :
```bash
python notifications.py                  # relances du jour + retard + alertes fin d'engagement
python notifications.py --resume-hebdo   # + résumé hebdomadaire (à lancer le lundi)
```
- Envoie par **email et/ou Telegram** la liste des relances (prospects + clients) du jour et en retard.
- Déclenche l'**alerte client automatique** (email HTML, avec offre alternative si économie identifiée) pour tout contrat atteignant le seuil de 60 jours avant fin d'engagement, et journalise l'action dans l'audit trail.
- Option résumé hebdomadaire : nombre de prospects/clients en base, économies totales estimées.
- Planification Windows : `schtasks /create /tn "IA Conseil - Relances" /sc daily /st 08:00 /tr "python C:\chemin\src\notifications.py"`. Planification cron : `0 8 * * * cd /chemin/src && python notifications.py`.

---

## ⚙️ Fonctionnalités clés en détail

### Moteur de comparaison (`offres_engine.py`)
```python
comparer_offres(univers, categorie, cout_actuel_mensuel, fournisseurs_autorises=None, fournisseur_exclu=None)
→ liste d'offres triées par économie annuelle décroissante
```
`construire_recommandations()` adapte l'offre principale et les cross-sell au service télécom recherché (Mobile / Box / Pack / Multi-lignes) — un service **Pack Box + Mobile** ne propose plus de cross-sell vers du Mobile ou du Box isolé (comparaison qui n'a pas de sens, le client perdrait l'autre service).

Coût de référence pour le cross-sell (`prospects_engine.cout_reference_categorie`) : une offre dont la catégorie correspond au service télécom principal déclaré se compare à `cout_mensuel_actuel` ; une offre cross-sell (catégorie différente, ex. Box proposée à un prospect Mobile) se compare à un contrat déjà connu du prospect dans cette catégorie (`contrats_engine.lire_contrats_prospect`) — sans ce contrat, aucune économie n'est affichée plutôt qu'un chiffre trompeur. `utils.economie_totale_groupee()` calcule l'économie totale d'un ensemble d'offres cochées en ne retenant que la meilleure offre par (univers, catégorie) avant de sommer entre catégories.

### Analyse de facture — trois moteurs (`pdf_engine.py` + `backend/services/facture_analyzer.py`)
- `analyser_facture(texte)` : détecte opérateur/fournisseur, prix, code postal/ville, nom du client, téléphone, email, data mobile — par expressions régulières, tolérant aux formats hétérogènes (PDF texte uniquement).
- `analyser_facture_vision(contenu, nom_fichier, api_key, model="claude-sonnet-5")` : mêmes champs, extraits par l'API **Claude Vision** — fonctionne sur PDF, JPG, PNG (photo/scan compris) ; retombe silencieusement sur `None` (→ fallback PyPDF2) si le package `anthropic`, la clé API ou le format sont absents/invalides ; **prioritaire** quand une clé API est disponible.
- `backend.services.facture_analyzer.analyser_facture()` (Claude Haiku, prompt few-shot, ~95%+ de précision visée) : appelé par `app.py` **en complément** du repli regex (PDF texte, sans clé Vision) pour enrichir uniquement les champs opérateur/prix/data — l'identité client (nom/tél/email/cp/ville) reste extraite par regex, ce service ne la couvre pas. Échoue silencieusement (retombe sur le regex seul) si la clé API, le fichier ou la réponse LLM posent problème.
- `analyser_speedtest_pdf()` : extrait débit descendant/montant.

### Génération PDF (`pdf_engine.py`)
- `generer_pdf_teaser()` : PDF "aperçu" envoyé après le diagnostic — économie totale chiffrée, sans détail des offres.
- `generer_pdf_restitution()` : PDF complet multi-pages, cartes d'offres détaillées + bandeau d'économie totale.
- `generer_pdf_devis()` / `generer_pdf_mandat()` : devis d'honoraires et mandat de représentation, générés depuis un enregistrement `factures`.

### Souscription
- **Lien affilié direct** (`utils.construire_lien_affilie`) : bouton « 🔗 Souscrire » sur toute offre disposant d'une URL de souscription, avec code d'affiliation et coordonnées client en paramètres d'URL ; chaque clic est tracé dans l'audit.
- **Pré-remplissage assisté** (`souscription_engine.py`, Playwright) : pour Free et Bouygues (`OPERATEURS_SUPPORTES`), ouvre un vrai navigateur visible (process détaché, indépendant de Streamlit) sur le formulaire de souscription du site opérateur, pré-rempli avec les coordonnées du prospect/client — le bouton **🖊️ Pré-remplir la souscription** est désormais toujours affiché dès qu'un lien de souscription existe (message clair si le fournisseur n'est pas automatisé, au lieu d'être masqué silencieusement).
- **Automatisation Free (éligibilité + choix de box)** : avant même le formulaire de coordonnées, `souscription_engine.py` remplit et valide le test d'éligibilité par adresse (cascade code postal → ville → voie → numéro, peuplée en AJAX, avec correspondance souple sur les accents/l'ordre des mots — le référentiel voirie de Free inverse parfois le nom de la voie), ferme la bannière cookies (Didomi/OneTrust/repli générique), puis clique sur la carte de box correspondant le mieux au nom de l'offre du catalogue. Le remplissage des coordonnées est ensuite retenté automatiquement toutes les 3 secondes pendant 15 minutes tant que la fenêtre reste ouverte (sans jamais écraser un champ déjà rempli), le temps que le conseiller valide les étapes intermédiaires (choix du Player TV…). À aucun moment la commande elle-même n'est soumise — validation humaine obligatoire jusqu'au bout.

### Réseau le plus fort par ville (`clients_engine.py`)
- `note_couverture_par_zone(ville)` : moyenne de satisfaction réseau déclarée par opérateur (prospects + clients de la ville).
- `meilleur_debit_par_zone(ville)` : moyenne des débits ⬇️/⬆️ mesurés par opérateur (même périmètre) — recommandation objective complémentaire à la satisfaction subjective.

### Relances
- Prospects : `widget_relance()` — bouton « Relance effectuée » (+7 j auto) + option repliée « Date de fin d'engagement » : la relance est alors calée automatiquement `RELANCE_JOURS_AVANT_ENGAGEMENT` (14) jours avant cette échéance (`date_relance_avant_engagement`), pour recontacter le prospect en temps utile plutôt qu'à une date arbitraire ; nouveau prospect toujours positionné sur aujourd'hui.
- Clients : `widget_relance_client()` — même principe, cadence par défaut +30 jours, activation manuelle depuis la fiche client.
- Relais hors app : `notifications.py` (voir section 10) envoie le digest quotidien même app fermée.

### Suivi de dossier local (`contrats_engine.py`, avant conversion en client)
Un contrat peut désormais être rattaché à un **prospect** (`prospect_id`) plutôt qu'à un client, avec deux usages distincts (`type_contrat`) :
- `reference_externe` (ou `NULL`) : un service que le prospect a déjà souscrit ailleurs, appris par le conseiller — sert uniquement de base de comparaison pour l'économie d'une offre cross-sell (voir `cout_reference_categorie` ci-dessus).
- `dossier_cmr` : le dossier en cours de vente avec nous, créé depuis la fiche prospect (sélection des offres « intéresse le client » retenues) et suivi via `ETAPES_CONTRAT` = **Documents reçus → Mandat envoyé → Mandat signé → Souscription en cours → Actif** (+ statut terminal « Résilié », accessible hors progression). Dès que ce dossier passe **Actif**, `finaliser_conversion_client()` convertit automatiquement le prospect en client : ses infos sont copiées, ses contrats de dossier migrés (`transferer_contrats_dossier_vers_client`), ses éventuelles références externes restantes supprimées (devenues inutiles), ses devis d'honoraires rattachés au nouveau client, et la fiche prospect supprimée.

Ce suivi est **entièrement local** (SQLite) — à ne pas confondre avec le dossier côté `backend/` ci-dessous, qui vit dans une base Postgres séparée et ajoute la génération d'un lien de portail client, un mandat d'honoraires structuré et l'analyse de facture par LLM.

### Lien personnel « transmettre facture + test de débit » (`prospects_engine.py`, `tokens_prospects`)
Depuis la fiche prospect, le conseiller peut générer un lien à usage personnel (`creer_token_documents`, `secrets.token_urlsafe(24)`, 14 jours de validité par défaut, non révocable pour l'instant côté UI mais la colonne `revoque` existe) et l'envoyer par SMS et/ou email (`notifications.envoyer_demande_documents_prospect`, selon les coordonnées disponibles). Le prospect ouvre une mini-page publique (`static/portail_prospect.html`, servie par `chatbot_api.py` sur `GET /portail/{token}`) sans aucune authentification autre que le token, et peut :
- transmettre sa facture (PDF/JPG/PNG) — analysée par regex (PDF texte) puis, si nécessaire et qu'une clé API est configurée, par Claude Vision (`analyser_facture_vision`) ;
- transmettre un test de débit (PDF ou capture d'écran) — analysé par regex puis Claude Vision (`analyser_speedtest_vision`, nouveau) ;
- télécharger le PDF « aperçu » de son économie estimée, régénéré à la volée (`construire_apercu_pdf_prospect`) — utile car un SMS ne peut pas porter de pièce jointe.

Chaque envoi met à jour la fiche prospect (opérateur/fournisseur/coût/data ou débits) et notifie immédiatement le conseiller par email/Telegram (`notifications.notifier_document_prospect_recu`), sans qu'il ait eu à les redemander par téléphone. `valider_token_documents()` journalise chaque utilisation (date, compteur) et rejette un token expiré ou révoqué.

### Pont Streamlit → backend (`api_client.py`, dossiers/mandats/facture LLM)
`api_client.py` distingue deux services HTTP totalement indépendants : `CRM_API_URL` (port 8003, `crm_api.py`, SQLite, avec repli local automatique) et `BACKEND_API_URL` (port 8000, `backend/main.py`, Postgres, **sans repli local possible**). Pour les fonctionnalités propres au backend, un client ou prospect SQLite est d'abord miroité côté Postgres (`_backend_client_id_pour`, mémorisé dans la colonne `backend_client_id` du client **ou** du prospect) avant tout appel. Fonctions exposées à `app.py` (fiche prospect et fiche client) :
- `creer_dossier()` / `lire_dossiers_client()` — ouvrir un dossier de suivi côté backend.
- `envoyer_lien_client(dossier_id, canal)` — génère et envoie le lien du portail client (`frontend-portail/`) par SMS ou email.
- `obtenir_dossier()` / `obtenir_timeline_dossier()` / `ajouter_note_dossier()` — détail, stepper et journal du dossier.
- `obtenir_briefing_client()` — vue agrégée (infos client + dossier en cours + dernière facture analysée) à consulter avant d'appeler.
- `obtenir_mandat_honoraires()` / `creer_mandat_honoraires()` / `marquer_signe_honoraires()` — mandat d'honoraires du dossier.
- `analyser_facture_client()` — envoie une facture PDF à `POST /factures/analyze` (multipart) et persiste le résultat, lié au client, pour le briefing.
- `lister_demarches()` / `creer_demarche()` / `generer_demarche()` / `envoyer_demarche()` / `renseigner_champs_demarche()` / `demarche_document_url()` — bloc **« 📮 Démarches »** de la fiche dossier (génération PDF puis envoi LRE, en 1 clic chacun, tâches Celery asynchrones côté backend).

En cas d'échec (backend non lancé, injoignable), ces appels lèvent `ApiIndisponible` : `app.py` l'attrape et affiche un message clair au conseiller plutôt que de planter — contrairement à `crm_api.py`, il n'y a ici **aucun repli sur SQLite**, ces données n'existant que côté Postgres.

### Veille prix (`veille_prix_engine.py`)
- `extraire_prix(texte)` : regex sur le texte de la page (pas de dépendance IA).
- `scraper_source(source)` / `_recuperer_texte_page()` : Playwright **headless**, isolé pour être simulé (monkeypatch) dans les tests sans navigateur réel.
- `lancer_veille()` : relève le prix de chaque source active, journalise toujours dans `veille_historique_prix`, crée une `veille_alertes` (`en_attente`) uniquement si l'écart dépasse `SEUIL_ECART_PRIX` (0,01 €). Ne touche jamais `offres` directement.
- `valider_alerte(alerte_id)` : seule fonction qui répercute le nouveau prix sur l'offre du catalogue (si la source y est rattachée) — action explicite d'un admin, tracée dans l'audit. `rejeter_alerte(alerte_id)` classe sans effet.
- Exécutable en tâche planifiée (voir en-tête du fichier pour les commandes `schtasks`/cron) ; notifie l'admin (email/Telegram) via `notifications.notifier_changement_prix()` à chaque changement détecté.

### Catalogue auto-alimenté (`catalogue_engine.py`)
À la différence de la veille prix ci-dessus (qui *suit* le prix d'une offre déjà connue), ce module **découvre** de nouvelles offres — c'est lui qui alimente le catalogue en continu plutôt que de dépendre d'une saisie manuelle (Admin > ➕ Ajouter une offre).
- `verifier_robots(url)` : vérifie `robots.txt` avant toute ingestion (`urllib.robotparser`) ; une source dont l'accès est interdit (`robots_ok=0`) est systématiquement ignorée par `ingerer_source`.
- `_recuperer_page(url, methode)` : `requests` par défaut (rapide, pages statiques) ou repli Playwright headless (`methode="playwright"`) si la page nécessite du JavaScript — isolée pour être simulée (monkeypatch) dans les tests. `html_vers_texte()` réduit ensuite le HTML à son texte lisible (BeautifulSoup, avec repli regex si le package est absent) avant envoi au LLM.
- `extraire_offres_llm(texte, source)` : appelle Claude (Haiku, sortie JSON contrainte par tool-use) pour extraire les offres présentes sur la page (fournisseur, nom, prix, engagement, data, caractéristiques…), avec un score de confiance et la liste des champs incertains par offre. **Garde-fou** : si aucun prix numérique clair n'est trouvé, le champ est laissé vide plutôt qu'inventé — l'offre est alors routée en statut `a_verifier`. Échoue silencieusement (`[]`) si le package/la clé API sont absents ou la réponse inexploitable.
- `normaliser_offre()` : mappe les libellés fournisseur/catégorie bruts du LLM vers les listes canoniques de `constants.py` quand une correspondance existe (insensible à la casse/aux accents), pour éviter les doublons de libellé (« SFR » vs « sfr »).
- `hash_contenu()` : empreinte SHA-256 (fournisseur + nom + prix + engagement) servant à la fois de clé de dédoublonnage (une offre déjà en attente n'est pas réinsérée) et de détection de changement (même offre, prix différent → liée à l'offre existante via `offre_existante_id` plutôt que dupliquée).
- `ingerer_source(source_id)` / `ingerer_toutes_sources_actives()` : fetch → extraction → normalisation → dédoublonnage → écriture dans `offres_staging` (jamais dans `offres` directement) ; renvoie un résumé (nouvelles offres / changements de prix / à vérifier / doublons ignorés).
- `valider_offre_staging(id)` : seule fonction qui répercute une offre en attente sur le catalogue — ajoute une nouvelle offre, ou met à jour le prix d'une offre existante si `offre_existante_id` est renseigné (action explicite d'un admin, tracée dans l'audit). `rejeter_offre_staging(id)` classe sans effet.
- Exécutable en tâche planifiée (voir en-tête du fichier pour les commandes `schtasks`/cron) ; notifie l'admin (email/Telegram) via `notifications.notifier_nouvelles_offres_staging()` dès qu'au moins une offre attend une validation.

### Agent d'audit autonome (`audit_agent.py`)
Assemble en un seul appel les briques jusqu'ici orchestrées à la main dans le wizard (comparaison, base de comparaison cross-sell, couverture réseau) pour produire une recommandation argumentée. **Principe non négociable** : le LLM n'a pas le droit de calculer ou d'affirmer un montant — il choisit quels outils appeler et rédige l'explication, jamais les chiffres.
- **Outils** (wrappers minces autour du code déjà testé, chacun renvoyant sa `source`) : `outil_comparer_offres` (→ `offres_engine.comparer_offres`, source = offre catalogue + date de mise à jour), `outil_cout_reference_categorie` (→ `prospects_engine.cout_reference_categorie` — renvoie `None` sans base de comparaison fiable, ex. cross-sell sans contrat connu : l'offre ne doit alors pas être recommandée), `outil_couverture_reseau` (→ `clients_engine.note_couverture_par_zone` + `meilleur_debit_par_zone`), `outil_calcul_economie` (→ `utils.economie_totale_groupee`), `outil_extraire_facture` (→ `pdf_engine.analyser_facture`, pour un usage API/headless futur — le wizard n'en a pas besoin, la situation est déjà extraite à l'étape 1).
- `lancer_audit(situation)` : boucle agentique Claude (même structure que `chatbot_engine.traiter_message`), garde-fou de 8 tours max, prompt système imposant la règle non négociable et l'obligation de vérifier `cout_reference_categorie` avant toute offre cross-sell. Se termine par un unique appel à l'outil `soumettre_audit` (situation détectée, offre_id retenus + explications, points d'attention, niveau de confiance).
- **Traçabilité renforcée** : contrairement à une conception où le LLM rapporterait lui-même sa traçabilité, `audit_agent.py` journalise réellement chaque appel d'outil pendant la boucle ; c'est ce journal (pas le LLM) qui reconstruit `economie_totale_an` (via `utils.economie_totale_groupee`) et `tracabilite[]` en fin de course — un `offre_id` que le LLM soumettrait sans être passé par `comparer_offres` est silencieusement ignoré (jamais affiché).
- Branché dans `app.py` (étape 4 du wizard) via un panneau **« 🤖 Audit automatique »**, additif et purement informatif : il ne pré-coche rien et ne génère aucun PDF — le conseiller garde la main sur le parcours manuel existant en dessous (cases « Intéresse le client », PDF).
- **Éval qualité** : `scripts/eval_audit.py` (10 cas dans `src/tests/cas_audit_eval/*.json`, catalogue de démo connu, comparaison ±5 % à l'attendu) — script manuel, volontairement **exclu de pytest/CI** (appelle réellement l'API, coût + non-déterminisme) : à relancer à la main après tout changement du prompt système, viser ≥ 8/10.

### API REST interne & découplage Streamlit (`crm_api.py`, `jwt_auth.py`, `api_client.py`)
- `jwt_auth.creer_token(user)` : émet un JWT (HS256, 8h) signé avec `CRM_API_SECRET` (secret de dev affiché en avertissement si absent).
- `jwt_auth.get_current_user` / `require_role(*roles)` : dépendances FastAPI qui protègent chaque route de `crm_api.py` (401 si jeton absent/invalide, 403 si rôle insuffisant).
- Chaque fonction d'`api_client.py` a exactement la même signature que son équivalent `*_engine.py` : `app.py` peut donc appeler l'un ou l'autre sans changement de logique. En cas d'échec réseau (`_ApiIndisponible`), repli **silencieux et automatique** sur l'accès direct à la base — un `st.toast` avertit une fois par session que l'API est injoignable.
- Le login Streamlit (formulaire + `st.session_state`) reste inchangé : un JWT est simplement émis localement (sans appel réseau) au moment de la connexion, et stocké dans `st.session_state.api_token` pour authentifier les futurs appels à `crm_api.py`.

### Scoring de priorité des prospects (`prospects_engine.py`)
```python
calculer_score_prospect(prospect, dernier_contact=None)
→ score = economie_estimee_an*2 + jours_depuis_dernier_contact*3
        + (satisfaction_basse ? +20 : 0) + (veut_rester ? -15 : 0)
        + (type_pro ? +10 : 0)
```
- `jours_depuis_dernier_contact` est déduit de l'historique d'audit (dernière relance effectuée/programmée sur ce prospect), ou à défaut de sa date de création.
- `recalculer_scores_prospects()` recalcule et persiste le score de tous les prospects (colonne `score`) — appelé à chaque affichage du Tableau de bord et de la liste Prospects.
- `indicateur_score(score)` renvoie l'étiquette visuelle 🔴 chaud / 🟡 tiède / 🟢 froid utilisée dans les tableaux et la fiche prospect.
- `expliquer_score_prospect()` détaille chaque composante du score en clair (économie, ancienneté du contact, bonus/malus) — affiché au conseiller dans la popup **🔍 Détails du prospect**, pour ne pas laisser le score comme un chiffre opaque.
- Sert à trier les relances par priorité business plutôt que par simple date d'échéance.

### Recherche plein texte
- Index **SQLite FTS5** sur `prospects` et `clients`, tenu à jour automatiquement.
- `recherche_fts(table, terme)` renvoie les IDs correspondants — utilisé dans les pages Prospects et Clients pour une recherche instantanée multi-champs (nom, ville, email, opérateur…).

### Facturation & mandat (`facturation_engine.py`)
- `creer_facture()`, `lire_factures()`, `maj_facture()`, `changer_statut()` (fixe automatiquement la date de paiement au premier passage à « Payé »), `marquer_mandat_signe()`.
- `lier_facture_a_client()` : rattache les devis existants d'un prospect au client créé lors de la conversion.

### Sécurité
- Mots de passe : PBKDF2-SHA256, 260 000 itérations, sel aléatoire par compte, comparaison en temps constant.
- Admin par défaut : mot de passe généré aléatoirement (`secrets.token_urlsafe(9)`, jamais codé en dur), changement forcé au premier login (`utilisateurs.doit_changer_mdp`).
- Rate limiting login réellement implémenté et persisté : `auth.authentifier_avec_limite()` — 5 échecs consécutifs (même identifiant + IP, table `login_tentatives`) → blocage 15 min, un succès plus récent qu'un échec réinitialise le compteur, historique purgé après 1 jour ; appliqué côté Streamlit **et** côté `crm_api.py`.
- Toute requête SQL utilise des paramètres liés (pas de concaténation) → pas d'injection SQL.
- Secrets (SMTP, clé API Anthropic, Telegram, SMS OVH/Twilio, `CRM_API_SECRET`) : priorité aux variables d'environnement (`.env`, `secrets_config.py`), repli sur la table `parametres` en base pour compatibilité ; jamais affichés en clair dans l'UI.
- `CRM_API_SECRET` obligatoire si `APP_ENV=production` — l'API refuse de démarrer sans lui plutôt que d'utiliser un secret de développement prévisible.
- Traçabilité systématique : `cree_par` sur chaque enregistrement + table d'audit insert-only (inclut les clics sur liens affiliés, les pré-remplissages de souscription, et les documents reçus via lien personnel).
- API interne (`crm_api.py`, port 8003) protégée par JWT ; API chatbot (`chatbot_api.py`) volontairement publique mais rate-limitée (30 req/min/IP) — le portail prospect (`/portail/{token}`) n'a pas de login mais exige un token valide, non expiré, non révoqué.

### Tests & CI
- Suite **pytest** (`src/tests/`) couvrant auth, moteur d'offres, utils, pdf_engine, prospects_engine, contrats_engine, souscription_engine, chatbot, notifications, sms_engine (`conftest.py` pour les fixtures communes).
- **GitHub Actions** (`.github/workflows/tests.yml`) : installe `requirements-dev.txt` et lance `pytest -q` à chaque push et pull request.

---

## 🤖 Chatbot public (diagnostic 24/7, `chatbot_api.py` + `chatbot_engine.py`)

Un second process, indépendant de Streamlit, partage la même base SQLite pour offrir un point d'entrée public (site web / futur WhatsApp) :

```bash
cd src
uvicorn chatbot_api:app --host 0.0.0.0 --port 8001
```

- `POST /api/chat` — fait progresser une conversation (`session_id`, `message`) ; Claude (tool-use, clé configurée dans Admin > OCR Vision — `anthropic_api_key`) collecte progressivement prénom/nom, contact, ville, et la situation Télécom/Énergie actuelle, puis crée le prospect (`origine='Chatbot'`) et notifie le conseiller (mêmes canaux email/Telegram que `notifications.py`).
- `POST /api/prospects`, `POST /api/offres/comparer`, `POST /api/bilan` — endpoints structurés réutilisables indépendamment du chat.
- `GET /docs` — documentation Swagger auto-générée.
- Widget d'intégration : `<script src="https://votre-api/widget/chatbot_widget.js" data-api-url="https://votre-api"></script>` (bulle de chat flottante, aucune dépendance).
- Aucune authentification sur ces endpoints (usage public assumé) — un limiteur de débit basique en mémoire (30 req/min/IP) protège contre le spam le plus simple ; CORS ouvert à tout domaine pour permettre l'intégration sur n'importe quel site.

---

## 🏗️ Backend FastAPI + Postgres (`backend/`) — Postgres réel branché, Sprint 3 (portail) livré

Second système, **en parallèle** de l'app Streamlit historique (pas un remplacement) : FastAPI + **Postgres Neon réel** (async SQLAlchemy) + Alembic + Celery, construit pendant les Sprints 2, 3, 4, 5 et 6 (partiel) de `ROADMAP_EXECUTION.md`. **L'auth et le CRUD prospects/clients/contrats/offres de Streamlit continuent de tourner entièrement en direct sur SQLite** (pas de bascule sur ce backend pour ces opérations) — mais `app.py` consomme désormais aussi ce backend **en HTTP** via `api_client.py` (voir §「Pont Streamlit → backend」dans la section précédente) pour : ouvrir un dossier, envoyer le lien du portail client par SMS/email, suivre sa timeline, gérer son mandat d'honoraires, et faire analyser une facture par le service LLM du backend (`facture_analyzer.py` reste aussi appelé en import Python direct, sans HTTP, en complément du regex à l'étape 1 du diagnostic). Le portail client Next.js (`frontend-portail/`, voir section suivante) consomme entièrement ce backend en HTTP.

| Fichier/dossier | Rôle |
|---|---|
| `backend/main.py` | Point d'entrée FastAPI (`uvicorn backend.main:app`), assemble les routers, CORS ouvert au portail Next.js |
| `backend/core/config.py` | Config Pydantic Settings (lue depuis `backend/.env`) : `DATABASE_URL`, `CRM_API_SECRET`, `ANTHROPIC_API_KEY`, `YOUSIGN_*`, `REDIS_URL`, `PORTAIL_CLIENT_BASE_URL`, `S3_*` (Scaleway), `STRIPE_*`, SMS (`SMS_PROVIDER`, `OVH_*`/`TWILIO_*`), `RESEND_*` |
| `backend/core/security.py` | JWT (partage la logique de `src/jwt_auth.py`), hash mot de passe (PBKDF2 260k, cohérent avec `src/auth.py`), `get_current_user` |
| `backend/core/database.py` | Moteur SQLAlchemy async, session Postgres (Neon, `connect_args={"statement_cache_size": 0}` requis pour le pooler PgBouncer) |
| `backend/models/` | Modèles SQLAlchemy : `User`, `Prospect`, `Client`, `Contrat`, `Offre`, `Mandat`, `Document`, `Dossier`, `TokenPublic`, `Commission`, `Abonnement`, `MandatHonoraires`, **`Demarche`** |
| `backend/routers/auth.py` | `/auth/login`, `/refresh`, `/forgot-password`, `/reset-password`, `/me` |
| `backend/routers/clients.py`, `prospects.py` | CRUD REST (JWT requis) + `GET /clients/{id}/briefing` (vue agrégée : infos client + dossier en cours + dernière facture analysée — consommée par la fiche client Streamlit) |
| `backend/routers/dossiers.py` | CRUD `/dossiers` + `/dossiers/{id}/transition` (machine à états) + `/dossiers/{id}/timeline` + `/dossiers/{id}/notes` (journal manuel) + `/dossiers/{id}/token-client` (génère le lien unique du portail) + `/dossiers/{id}/envoyer-lien-client` (envoie ce lien par SMS ou email réels, cf. `notification_engine`) — JWT requis (conseiller) |
| `backend/routers/honoraires.py` | `GET/POST /dossiers/{id}/mandat-honoraires` + `POST /dossiers/{id}/mandat-honoraires/marquer-signe` — mandat d'honoraires du dossier (JWT requis) |
| `backend/routers/demarches.py` | `GET/POST /dossiers/{id}/demarches` (liste + création), `GET /demarches/{id}`, `POST /demarches/{id}/generer` et `/envoyer` (dispatch Celery, async), `PATCH /demarches/{id}/champs`, `GET /demarches/{id}/document` (URL signée) — génération et envoi tracé (LRE) des documents de démarche (mandat, résiliation, portabilité, changement de fournisseur, souscription), JWT requis |
| `backend/routers/portail_public.py` | `/portail/{token}` (contexte, inclut désormais `demarches_a_completer`), `/portail/{token}/documents` (upload + KYC auto), `/portail/{token}/suivi` (timeline), `/portail/{token}/demarches/{id}/champs` (le client renseigne RIO/PDL/PCE/RIB, filtré sur les clés attendues) — **accès par lien unique, sans login** |
| `backend/routers/factures.py` | `POST /factures/analyze` — analyse de facture par LLM (JWT requis), consommée à la fois par le portail (KYC) et par la fiche client Streamlit (`api_client.analyser_facture_client`) |
| `backend/routers/webhooks.py` | `POST /webhooks/yousign` — met à jour le statut de signature d'un mandat (signature HMAC vérifiée, pas de JWT) |
| `backend/services/facture_analyzer.py` | Appel Claude Haiku, prompt few-shot, JSON structuré (opérateur, prix HT/TTC, data, options, engagement, IBAN) — déjà consommé par `src/app.py` en complément du regex |
| `backend/services/kyc_engine.py` | Validation KYC par Claude Haiku Vision (CNI valide / JDD < 3 mois / RIB au bon nom) — appelé automatiquement à chaque upload sur le portail client |
| `backend/services/signature_engine.py` | Wrapper API Yousign v3 (créer/envoyer/télécharger un mandat) |
| `backend/services/dossier_engine.py` | Machine à états du workflow de souscription (`initie → docs_demandes → docs_recus → mandat_a_signer → mandat_signe → soumis_fournisseur → en_activation → actif → facture`, + `echec`/`annule` depuis tout état non terminal) ; journalise chaque transition (`notes_workflow`), construit la liste des documents requis par univers et la timeline affichée au client |
| `backend/services/token_engine.py` | Génère/valide le token public du portail (`secrets.token_urlsafe(32)`, 30 jours de validité par défaut, révocable, IP et date de première/dernière utilisation journalisées) |
| `backend/services/storage_engine.py` | Upload/téléchargement des documents client sur S3 (Scaleway Object Storage recommandé), chiffrement SSE-AES256 côté serveur, clés d'objet non devinables, URLs signées à durée limitée ; `upload_fichier()` généralise ce stockage aux fichiers non rattachés à un client (ex. documents de démarche rattachés à un dossier) |
| `backend/services/notification_engine.py` | Envoi **réel** email (Resend) et SMS (OVH ou Twilio, mêmes principes que `src/sms_engine.py`) — dégrade proprement (renvoie `False`, ne lève jamais) si non configuré |
| `backend/services/dossier_notifications.py` | Templates email/SMS par statut de dossier (`TEMPLATES_STATUT`), envoyés automatiquement à chaque transition (`notifier_transition`) et lors d'une relance de stagnation (`notifier_relance`, seuils `SEUILS_JOURS_PAR_STATUT` par statut) |
| `backend/services/demarches_engine.py` | Logique métier des démarches post-vente : `demarches_requises(dossier)` (mapping univers → types de démarche attendus), `champs_manquants(demarche)`, `creer_demarche()`, `marquer_champs()`, `generer_document()` — **refuse (lève `DemarcheEngineError`) tant que le mandat de représentation du client n'est pas `signe`**, règle légale non négociable |
| `backend/services/document_engine.py` | Génération PDF (fpdf2, indépendant de `src/pdf_engine.py`) des documents de démarche : `generer_pdf_mandat_representation`, `generer_pdf_resiliation_box`, `generer_pdf_demande_portabilite_mobile`, `generer_pdf_changement_fournisseur_energie`, `generer_pdf_souscription` — chaque type déclare ses champs requis (`CHAMPS_REQUIS_PAR_TEMPLATE`, ex. RIO pour la portabilité, RIB pour le changement de fournisseur) |
| `backend/services/lre_engine.py` | Wrapper API **AR24** (lettre recommandée électronique) : `envoyer_lre()`, `verifier_statut_lre()`, `telecharger_preuve_depot()` — **lève `LreEngineError`** (y compris si non configuré) plutôt que de dégrader silencieusement comme `notification_engine`, car la LRE est le canal légalement requis pour ces démarches |
| `backend/workers/` | Celery : `valider_document_kyc`, `envoyer_mandat_signature`, `telecharger_mandat_signe`, **`generer_document_demarche`, `envoyer_demarche_lre`** (retry auto) + tâches planifiées (`beat_schedule`) : relance quotidienne (8h00) des dossiers stagnants, et **vérification horaire des accusés de réception LRE** (`verifier_accuses_lre_en_attente` — AR24 ne garantissant pas de webhook aussi fiable que Yousign, le polling est le repli retenu) ; broker/backend Redis |
| `backend/alembic/` | Migrations : `0001_initial_schema` (miroir du schéma SQLite), `0002_mandats_documents`, `0003_dossiers_tokens_commissions` (tables `dossiers`, `tokens_publics`, `commissions`, `abonnements`), `0004_factures_analysees`, `0005_dossier_relances`, `0006_mandats_honoraires`, **`0007_demarches`** (table `demarches`), **`0008_tokens_publics_demarches`** (flag `peut_renseigner_demarches`) — 0001 à 0006 appliquées avec succès sur Postgres Neon, 0007/0008 à appliquer (`alembic upgrade head`) |
| `backend/tests/` | Tests mockés (Anthropic, DB) — passent sans Postgres réel |

**Ce qui manque encore** (détail complet et à jour dans `IA_CONSEIL_UTILISATION.md` §12.0/§12) :
- Chiffrement `pgcrypto` des colonnes PII (CNI, IBAN) — pas encore dans les migrations (les documents uploadés sont déjà chiffrés côté S3).
- Script `migrate_sqlite_to_postgres.py` (pas encore écrit).
- Bascule effective de `src/app.py` sur ce backend pour l'**auth/CRUD** clients/prospects (aujourd'hui : accès direct SQLite pour ces opérations — choix assumé, pas un oubli). En revanche, dossiers, mandats d'honoraires et analyse de facture LLM sont déjà **consommés depuis Streamlit** via `api_client.py` (voir §「Pont Streamlit → backend」).
- Compte Yousign réel, compte S3/Scaleway réel, compte Anthropic réel pour tester KYC/signature/upload en conditions réelles avec un vrai client.
- CSP stricte sur le portail Next.js (voir section suivante).
- Compte **AR24** réel pour tester l'envoi LRE des démarches en conditions réelles (`backend/services/lre_engine.py`) — schéma d'authentification exact (bearer token vs login/mot de passe) et vocabulaire de statut à vérifier contre la doc AR24 avant mise en prod.
- Relecture par l'avocat des textes de courrier générés par `backend/services/document_engine.py` (mandat, résiliation, portabilité, changement de fournisseur) — boilerplate raisonnable, même statut que le mandat existant de `src/pdf_engine.py`, jamais validé juridiquement à ce jour.

Commandes détaillées (installation, migrations, lancement, tests) : voir `IA_CONSEIL_UTILISATION.md` §12.

---

## 🖥️ Portail client (`frontend-portail/`, Next.js) — Sprint 3, livré

Troisième process indépendant (Next.js 14, App Router, TypeScript, Tailwind), destiné au **client final** — pas au conseiller. Accessible **sans login** via un lien à token unique que le conseiller génère depuis le CRM et envoie par SMS/email (choix assumé, plus simple qu'un compte client avec mot de passe).

**Parcours client :**
1. Le conseiller crée un dossier (`POST /dossiers`) puis génère un lien (`POST /dossiers/{id}/token-client`) → récupère une URL du type `http://localhost:3000/dossier/<token>` (30 jours de validité) et un message SMS suggéré.
2. Le client ouvre le lien (aucune authentification, le token fait foi) : `frontend-portail/app/dossier/[token]/page.tsx` affiche son prénom, l'économie annuelle estimée, la liste des documents à fournir (statut `à fournir` / `en attente` / `validé` / `à refaire` avec motif) et le statut de son mandat.
3. S'il reste des documents à fournir, un bouton mène vers `/dossier/[token]/documents` : upload par glisser-déposer (PDF/JPG/PNG, 10 Mo max), chaque fichier est envoyé à `POST /portail/{token}/documents`, stocké chiffré sur S3, puis **validé automatiquement par Claude Vision** (`kyc_engine.valider_document`) — retour immédiat à l'écran (validé / motif de rejet / en attente de vérification manuelle).
4. `GET /portail/{token}/suivi` (non encore branché dans une page dédiée du portail, disponible côté API) expose une timeline complète de l'avancement du dossier, calculée par `dossier_engine.construire_timeline()`.
5. S'il manque des informations pour une démarche en attente de génération (RIO pour une portabilité, PDL/PCE/RIB pour un changement de fournisseur…), un bandeau **« Compléter mes informations »** mène vers `/dossier/[token]/demarches` : un formulaire par démarche, soumis à `POST /portail/{token}/demarches/{id}/champs` (clés filtrées sur celles attendues par la démarche, jamais de champ arbitraire accepté).

| Fichier | Rôle |
|---|---|
| `frontend-portail/app/page.tsx` | Landing page (rappel : accès uniquement via lien personnel) |
| `frontend-portail/app/dossier/[token]/page.tsx` | Contexte du dossier (Server Component, `force-dynamic`) : accueil, économie estimée, statut des documents, statut du mandat |
| `frontend-portail/app/dossier/[token]/documents/page.tsx` | Upload des documents (Client Component), retour KYC en direct par document |
| `frontend-portail/app/dossier/[token]/demarches/page.tsx` | Formulaire de complément d'informations par démarche (RIO, PDL/PCE, RIB…), un formulaire par démarche en attente de champs |
| `frontend-portail/lib/api.ts` | Client HTTP typé vers `backend/routers/portail_public.py` (`getContexte`, `uploadDocument`, `soumettreChampsDemarche`) |
| `frontend-portail/next.config.js` | `NEXT_PUBLIC_API_URL` (défaut `http://localhost:8000`) |

Sécurité portail : token 256 bits (`secrets.token_urlsafe(32)`), expiration 30 jours, révocable, IP journalisée à chaque accès, aucune donnée interne conseiller (commissions, autres clients) exposée dans les réponses `portail_public` — voir `backend/schemas/portail_public.py`.

Commandes détaillées (installation, lancement) : voir `IA_CONSEIL_UTILISATION.md` §12.6.

---

## 🐳 Industrialisation & déploiement

Chantier 4 : les 3 process (Streamlit, backend, portail) restaient jusqu'ici des scripts locaux
sans conteneurisation, sans logs structurés, sans supervision d'erreurs ni monitoring des tâches
Celery, avec une CI qui ne faisait tourner que les tests Streamlit. Objectif : rendre le tout
déployable, observable et robuste sans changer l'architecture (toujours 3 process indépendants).

| Fichier/dossier | Rôle |
|---|---|
| `backend/Dockerfile` | Image FastAPI + Celery (même image pour `web`/`worker`/`beat`, commande différente à l'exécution) — contexte de build = racine du dépôt |
| `src/Dockerfile` | Image Streamlit, **Playwright + Chromium installés** (`playwright install --with-deps chromium`) : souscription assistée, veille prix et catalogue auto-alimenté fonctionnent aussi depuis ce conteneur — image volontairement plus lourde (~500 Mo de plus), décision assumée |
| `frontend-portail/Dockerfile` | Build Next.js multi-stage, `output: "standalone"` (`next.config.js`) pour un runtime minimal — contexte de build = `frontend-portail/` lui-même |
| `docker-compose.yml` | Environnement de **dev** : `redis`, `backend` (`--reload`), `celery-worker`, `celery-beat`, `flower`, `streamlit`, `postgres` (profil `local-db`, optionnel — `backend/.env` pointe sur Neon par défaut) |
| `.dockerignore` (racine) + `frontend-portail/.dockerignore` | Excluent `.env`, `*.db`, `node_modules`, `.venv`, etc. des images |
| `backend/core/logging.py` | `configurer_logging()` — un log JSON par ligne sur stdout (exploitable par n'importe quel agrégateur de logs des plateformes visées), appelé au chargement de `backend/main.py` **et** `backend/workers/celery_app.py` (process séparé) |
| Sentry (`sentry-sdk`) | Initialisé côté `backend/main.py`, `backend/workers/celery_app.py` (intégration `CeleryIntegration`) et `src/app.py` (via `secrets_config.sentry_dsn()`) — **no-op tant que `SENTRY_DSN` n'est pas renseigné**, jamais bloquant en dev |
| Sentry Next.js (`@sentry/nextjs`) | `instrumentation-client.ts`, `sentry.server.config.ts`, `sentry.edge.config.ts`, `instrumentation.ts`, `app/global-error.tsx` (capture les erreurs de rendu React côté App Router) — build vérifié sans erreur/avertissement (`npm run build`) |
| CSP (`frontend-portail/next.config.js`) | `headers()` : Content-Security-Policy resserrée (`default-src 'self'`, `connect-src` limité à l'API backend + Sentry), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` — garde `'unsafe-inline'` sur `script-src`/`style-src` (bootstrap Next.js), pas encore un CSP nonce-based strict |
| Idempotence Celery (`backend/workers/tasks.py`) | `envoyer_mandat_signature` et `envoyer_demarche_lre` vérifient désormais le statut déjà atteint (`envoye`/`signe`/`refuse` ou `envoyee`/`accusee`) avant d'appeler Yousign/AR24 — une tâche rejouée (retry après crash, relance manuelle) ne double plus un envoi. Les autres tâches (KYC, génération de document, téléchargement, relances) étaient déjà naturellement idempotentes |
| `pyproject.toml` | Config `ruff` (`line-length = 130`, `target-version = "py311"`) — **lint scopé à `backend/`** : `src/app.py` (211 Ko, jamais linté) en est volontairement exclu, dette assumée et non un oubli |
| `backend/requirements-dev.txt` | Nouveau (même pattern que `src/requirements-dev.txt`) : `pytest`, `pytest-cov`, `ruff` |
| `.github/workflows/tests.yml` | Étendu : `pytest-streamlit` (job existant), **`pytest-backend`** (`backend/tests/` désormais exécuté en CI — ne l'était pas jusqu'ici), **`lint`** (`ruff check backend`), **`docker-build`** (build des 3 images, sans push, aucun registre configuré) |
| `DEPLOIEMENT.md` | Procédure de déploiement : backend+Celery sur **Fly.io** (`fly.toml` d'exemple, process `app`/`worker`/`beat` séparés), portail sur **Vercel**, Streamlit sur Streamlit Community Cloud ou même hébergeur conteneur derrière auth, Postgres **Neon** (PITR/branching, procédure de test de restauration), Redis **Upstash**, S3 Scaleway (versioning, Object Lock), `/health` → UptimeRobot, Flower jamais exposé publiquement en prod |

**Ce qui manque encore** :
- Aucun compte réel créé (Fly.io, Vercel, Upstash, Sentry, UptimeRobot) — `DEPLOIEMENT.md` documente
  la procédure, ne constate pas un déploiement effectué.
- DSN Sentry non généré à ce jour (les 3 intégrations sont en place mais inertes tant que
  `SENTRY_DSN`/`NEXT_PUBLIC_SENTRY_DSN` ne sont pas renseignés).
- Test de restauration Neon (PITR) non exécuté.
- Object Lock S3 à vérifier sur le bucket existant (doit être activé à la création — potentiellement
  à recréer un bucket dédié aux documents les plus sensibles).
- CSP nonce-based strict (durcissement possible via `middleware.ts`, non fait — la CSP actuelle
  reste `'unsafe-inline'` sur scripts/styles).
- `docker compose build`/`up` non vérifié sur une machine avec Docker installé (absent de
  l'environnement où ces fichiers ont été écrits) — à valider avant premier usage réel.

---

## 📊 Sorties du logiciel

- Fiche prospect / client complète avec historique d'actions
- PDF "aperçu" (économie totale) + PDF de restitution complète (après paiement du devis) + email HTML
- Devis d'honoraires PDF + mandat de représentation PDF
- Contrats liés à chaque client (création, modification, suppression)
- Exports Excel (listes prospects/clients)
- Tableau de bord commercial temps réel (KPIs, relances, performance équipe)
- Digest quotidien de relances (email/Telegram) + alertes automatiques de fin d'engagement, via `notifications.py`

---

## 🎬 Vision à terme

Les phases 1 à 4 de la roadmap **d'origine** (fondations, automatisations, IA — chatbot, veille prix, API REST interne) sont **toutes livrées** — détail dans `IA_CONSEIL_ROADMAP.md` (document historique).

Un plan bien plus large est désormais en cours d'exécution, détaillé sprint par sprint dans **`ROADMAP_EXECUTION.md`** (4 phases sur 12 mois : sécurisation + Postgres/FastAPI + portail client Next.js + signature/KYC + LLM factures, puis automatisation télécom/énergie, puis scale + verticales B2B, puis ORIAS/assurance). État réel au 24/07/2026 : Sprint 1 (sécurisation code) **terminé** (rate limiting login et changement de mot de passe forcé réellement en base, plus seulement documentés), Sprint 2 (Postgres/FastAPI) **branché sur un vrai Postgres Neon**, Sprint 3 (**portail client Next.js**, `frontend-portail/`) **livré et testé bout-en-bout** (génération de lien → upload documents → KYC auto), Sprint 5 (LLM factures) **branché en HTTP** depuis la fiche client Streamlit (`POST /factures/analyze`) en plus de l'appel Python direct dans le diagnostic, Sprint 4 (signature/KYC) écrit et déjà branché sur l'upload du portail mais non testé avec de vrais comptes Yousign/S3, Sprint 6 (notifications + 1er dossier réel) **notifications email/SMS automatiques par statut de dossier écrites** (`notification_engine.py`, `dossier_notifications.py`, relance quotidienne des dossiers stagnants via Celery beat) — reste à tester avec de vrais comptes Resend/OVH/Twilio. En parallèle de ce plan, deux évolutions propres à l'app Streamlit ont été ajoutées côté `src/` : un **suivi de dossier 100% local** (contrats prospect, conversion automatique en client) et un **lien à usage personnel** pour que le prospect transmette lui-même sa facture/son test de débit. Tâches précises restantes : voir `IA_CONSEIL_UTILISATION.md` §12.0 et `SETUP_STATUS.md`.
