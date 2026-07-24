# IA CONSEIL — Roadmap d'exécution (fichier de travail Claude Code)

> **Source** : `IA_Conseil_Roadmap_Complete.pdf` (v1 — 10/07/2026)
> **Objectif de ce fichier** : transformer la roadmap stratégique en **checklist opérationnelle** utilisable directement avec Claude Code, sprint par sprint, tâche par tâche.
>
> **Comment l'utiliser** :
> 1. Ce fichier est ta **source de vérité opérationnelle**. Toujours le garder ouvert.
> 2. Pour chaque tâche, un bloc **"Prompt Claude Code"** est fourni — copie-colle direct.
> 3. Coche `[x]` au fur et à mesure. Ne saute jamais l'étape "vérification".
> 4. À la fin de chaque sprint : décision **Go / No-Go** avant de passer au suivant.

---

<a id="etat-avancement"></a>
## État d'avancement (mis à jour le 2026-07-21)

> Constat fait en relisant le code réel (`git diff`, arborescence `backend/`, `frontend-portail/`) — pas une auto-déclaration. Détail des cases cochées ci-dessous dans chaque sprint (celles des sprints 3 et 6 restent à jour dans le détail : le texte du résumé ci-dessous fait foi pour l'avancement réel, en attendant).

**Résumé** :
- ✅ **Sprint 1 (sécurisation code)** — quasi terminé côté code : secrets sortis de `session_state`/DB vers `.env` (`src/secrets_config.py`), rate limiting login (`login_tentatives` + `authentifier_avec_limite`), admin par défaut avec mot de passe aléatoire + changement forcé, `CRM_API_SECRET` obligatoire en prod. Suite pytest étoffée (`src/tests/`, 125 tests). **Reste** : tout le volet juridique (avocat, SAS, CGU, RGPD) + HTTPS/déploiement.
- ✅ **Sprint 2 (Postgres + FastAPI)** — squelette `backend/` complet (config, security, database, models User/Prospect/Client/Contrat/Offre/Mandat/Document/**Dossier/TokenPublic/Commission/Abonnement**, routers auth/clients/prospects/dossiers/portail_public/webhooks, Alembic avec 3 migrations) **et Postgres Neon réellement provisionné** : `alembic upgrade head` exécuté avec succès (`0003` en tête), `/auth/login`/`/clients`/`/prospects` exécutent de vraies requêtes SQL. **Reste** : pas de script `migrate_sqlite_to_postgres.py`, pas de chiffrement `pgcrypto` sur les colonnes PII, Streamlit `app.py` tourne toujours sur SQLite en direct pour l'auth/CRUD (bascule volontairement pas retenue à ce stade — voir `IA_CONSEIL_UTILISATION.md` §12).
- ✅ **Sprint 3 (portail client Next.js)** — livré : `frontend-portail/` (Next.js 14.2.35, App Router, TypeScript, Tailwind), pages `/`, `/dossier/[token]` (contexte + timeline), `/dossier/[token]/documents` (upload avec retour KYC en direct). Backend : `dossier_engine`/`token_engine`/`storage_engine` (S3 Scaleway, SSE-AES256), routers `dossiers` (JWT, génère le lien unique) et `portail_public` (accès par token, sans login). `npm run build` vérifié. **Écart assumé vs plan d'origine** : lien à token unique plutôt que login magic-link/SMS + compte client (plus simple, pas de mot de passe côté client). **Reste** : CSP stricte sur le portail (l'envoi SMS/email automatique du lien est fait, voir Sprint 6).
- 🟡 **Sprint 4 (signature + KYC)** — `backend/services/signature_engine.py` (wrapper Yousign v3) et `backend/services/kyc_engine.py` (validation Claude Haiku vision) écrits et déjà branchés sur l'upload du portail (`portail_public.uploader_document` appelle `kyc_engine.valider_document` en direct), tables `mandats`/`documents` migrées, Celery+Redis configurés (`backend/workers/`). **Reste** : génération PDF du mandat, bouton "Envoyer mandat" côté Streamlit, tests sur ces deux services, compte Yousign réel + template validé avocat.
- 🟡 **Sprint 5 (analyse facture LLM)** — `backend/services/facture_analyzer.py` écrit avec prompt few-shot + `backend/tests/test_facture_analyzer.py` (3 fixtures, client Anthropic mocké). `backend/routers/factures.py` créé (endpoint `POST /factures/analyze`, JWT-protégé, enregistré dans `main.py`), avec `backend/tests/test_factures_router.py` (4 tests, auth mockée). Streamlit (`src/app.py`, étape 1 du diagnostic) appelle ce service en complément du repli regex `pdf_engine.analyser_facture()` — uniquement pour les champs opérateur/prix/data. **Reste** : pas de mesure de taux de réussite sur factures réelles (30 factures télécom/énergie), l'endpoint `/factures/analyze` n'a toujours pas de consommateur HTTP réel (le portail Next.js n'appelle pas cette route — seul l'appel Python direct depuis Streamlit est branché).
- 🟡 **Sprint 6 (notifications + 1er dossier réel)** — la machine à états `dossiers` est faite (`backend/services/dossier_engine.py`, table `dossiers` migrée, transitions tracées dans `notes_workflow`) **et les notifications automatiques par étape sont maintenant branchées** (livré le 2026-07-21) : templates email/SMS par statut (`backend/services/dossier_notifications.py::TEMPLATES_STATUT`), déclenchés automatiquement à chaque transition (`dossier_engine.transiter(..., on_transition=...)`, appelé depuis `POST /dossiers/{id}/transition`) — en s'appuyant sur `backend/services/notification_engine.py` qui existait déjà (envoi OVH/Twilio + Resend), donc pas besoin d'un module `sms_engine.py` séparé côté backend. **Nouveau, au-delà du scope initial de ce sprint** : relance automatique si un dossier stagne trop longtemps sur un statut (`relancer_dossiers_stagnants`, tâche Celery planifiée tous les jours à 8h via `celery_app.beat_schedule` — nécessite de lancer `celery -A backend.workers.celery_app beat` en plus du worker), mandat d'honoraires (`mandats_honoraires`, migration `0006`) synchronisé automatiquement avec la signature Yousign du mandat de représentation (webhook), et un panneau conseiller unifié côté Streamlit (`src/app.py`, « 📄 Où en est ce dossier ») avec stepper visuel, statut des deux mandats et historique horodaté (transitions + notes manuelles + relances auto). Livré en même temps, côté legacy uniquement (indépendant du backend, pas de donnée à migrer) : export Excel + vue imprimable de l'agenda d'appels conseiller (`src/app.py`, pour le point d'équipe hebdo). **Reste** : comptes Twilio/OVH/Resend réels non configurés (dégradation gracieuse en attendant — aucun envoi ne part mais rien ne plante), pas encore de vrai dossier client testé bout-en-bout.
- ⬜ **Phases 2 à 4** — pas commencées.
- ✅ **Chantier 3 — Génération automatique des démarches** (livré le 2026-07-24, hors numérotation Sprint 1-24 de ce fichier — issu de `ROADMAP_AUTOMATISATION.md`, document de roadmap séparé) : table `demarches` (migrations `0007`/`0008`), moteur `backend/services/demarches_engine.py` (refuse la génération tant que le mandat de représentation du client n'est pas `signe` — règle légale), génération PDF (`document_engine.py`, fpdf2, un template par type : mandat/résiliation/portabilité/changement de fournisseur/souscription) et envoi tracé par LRE (`lre_engine.py`, wrapper **AR24**), tâches Celery (`generer_document_demarche`, `envoyer_demarche_lre`, polling horaire des accusés), routeur `backend/routers/demarches.py` (JWT), bloc conseiller « 📮 Démarches » dans `src/app.py`, collecte des champs manquants (RIO/PDL/PCE/RIB) sur le portail client Next.js. Suite `backend/tests/test_demarches_*.py` verte, aucune régression sur `src/`/`backend/tests` existants. **Reste** : compte AR24 réel (schéma d'authentification à vérifier), relecture avocat des textes de courrier, test bout-en-bout avec un vrai dossier.

**Prochaine étape logique** : configurer les comptes SMS/email réels (Twilio ou OVH, Resend — voir `IA_CONSEIL_UTILISATION.md` §12.0, le code d'envoi est déjà écrit), lancer `celery -A backend.workers.celery_app beat` pour activer les relances automatiques, puis recruter un premier vrai dossier client pour valider le parcours de bout en bout. Détail des correctifs restants : `SETUP_STATUS.md`.

---

## Sommaire

- [Étape 0 — Décisions bloquantes avant de coder](#étape-0)
- [Vue d'ensemble — les 4 phases (12 mois)](#vue-densemble)
- [Phase 1 — Fondations (mois 1-3)](#phase-1)
  - Sprint 1 · Fondations légales & juridiques
  - Sprint 2 · Migration SQLite → Postgres + FastAPI
  - Sprint 3 · Portail client MVP (Next.js)
  - Sprint 4 · Signature électronique + KYC
  - Sprint 5 · Analyse facture LLM
  - Sprint 6 · Notifications + 1er dossier bout-en-bout
- [Phase 2 — Automatisation télécom + énergie (mois 4-6)](#phase-2)
- [Phase 3 — Scale + verticales B2B (mois 7-9)](#phase-3)
- [Phase 4 — ORIAS + Assurance (mois 10-12)](#phase-4)
- [Chantiers transverses (à faire en continu)](#chantiers-transverses)
- [KPIs à suivre dès le 1er dossier](#kpis)
- [Budget infrastructure attendu](#budget)
- [Décisions en attente de ta réponse](#décisions)

---

<a id="étape-0"></a>
## Étape 0 — Décisions bloquantes AVANT de coder

Ces 5 points doivent être validés avant de lancer le Sprint 1. Sans eux, tout le reste est à risque.

- [ ] **Avocat spécialisé droit du numérique + consommation** — RDV pris (budget ~1 500 €)
- [ ] **SAS créée** + RC pro souscrite + mention "mandataire non exclusif" dans CGU
- [ ] **Comptes ouverts** : Neon (Postgres), Scaleway (S3), Vercel (Next.js), Yousign (signature), Anthropic (Claude API), Stripe (facturation), Resend (email), Twilio ou OVH (SMS)
- [ ] **Budget dev/mois défini** (temps perso + prestations externes éventuelles)
- [ ] **Choix tranché** : on part sur stack hybride confirmée (Streamlit conseiller + FastAPI + Postgres + Next.js portail)

---

<a id="vue-densemble"></a>
## Vue d'ensemble — les 4 phases

| Phase | Mois | Focus | Sprints |
|---|---|---|---|
| **P1 — Fondations** | 1-3 | Base légale, refacto DB, portail MVP, KYC, signature, LLM factures | S1 → S6 |
| **P2 — Auto télécom + énergie** | 4-6 | Contrats apporteurs, Stripe, veille tarifaire, upsell Gestionnaire | S7 → S12 |
| **P3 — Scale + B2B** | 7-9 | Alarme, TPE, alertes renouvellement, énergie pro, chatbot, dashboard commissions | S13 → S18 |
| **P4 — ORIAS + Assurance** | 10-12 | Formation IAS, grossistes assurance, mutuelle collective, cross-sell | S19 → S24 |

**Règle d'or** : chaque sprint = 2 semaines, un livrable concret, décision Go/No-Go à la fin.

---

<a id="phase-1"></a>
## PHASE 1 — Fondations (mois 1 à 3)

### Sprint 1 (sem 1-2) — Fondations légales & sécurisation code

**Objectif** : mise en conformité juridique + fix des vulnérabilités CRITIQUES du code actuel.

**Livrables** :
- SAS créée, RC pro active
- Mandat de représentation rédigé par avocat
- CGU + politique RGPD publiées
- Vulnérabilités CRITIQUES du code actuel corrigées

#### Tâches juridiques (à faire en parallèle du code)
- [ ] RDV avocat spécialisé — brief : mandat multi-univers + double rémunération (commission fournisseur + % économies) + délai rétractation 14j
- [ ] Rédaction mandat de représentation (contenu obligatoire : identité, objet précis, durée 12 mois, rémunération transparente, rétractation, eIDAS avancé, archivage 10 ans)
- [ ] CGU + politique confidentialité (français, claire)
- [ ] Registre des activités de traitement (RGPD art. 30)
- [ ] Identifier bases légales pour chaque traitement (consentement / exécution contrat / obligation légale)

#### Tâches code — sécurité applicative
- [x] **CRITIQUE** — Sortir mots de passe SMTP de `session_state`, passer en `.env` + `python-dotenv` — fait (`src/secrets_config.py`, `.env.example`, repli DB conservé pour compat)
- [x] **CRITIQUE** — Ajouter rate limiting login (max 5 tentatives / 15 min / IP+compte, compteur en DB + timeout) — fait (`login_tentatives` table dans `db.py`, `authentifier_avec_limite()` dans `auth.py`, branché dans `app.py` et `crm_api.py`)
- [x] **CRITIQUE** — Auditer `app.py` pour tous les autres secrets en clair et les migrer — fait pour `ANTHROPIC_API_KEY`, `CRM_API_SECRET` (obligatoire en prod, `jwt_auth.py`), Telegram ; admin par défaut passe d'un mot de passe en dur à un mot de passe aléatoire + changement forcé au 1er login
- [x] Créer suite pytest minimale : couverture sur `auth.py`, `clients_engine.py`, `db.py` — fait mais partiel : `src/tests/` (11 fichiers, ~1130 lignes) couvre `auth.py`, `crm_api.py` (donc indirectement `clients_engine.py`), prospects/offres/souscription/veille_prix/chatbot/pdf_engine/utils ; pas de test dédié à `db.py`
- [ ] Ajouter HTTPS (reverse proxy nginx + Let's Encrypt OU déploiement Fly.io / Streamlit Cloud avec TLS auto)

**Prompt Claude Code** :
```
Lis app.py, auth.py et jwt_auth.py. Identifie TOUS les endroits où un secret
(mot de passe, clé API, token) est stocké en session_state, en dur, ou lu
depuis un endroit non sécurisé. Sors la liste avec fichier:ligne. Ensuite,
propose un plan de migration vers .env + python-dotenv (dev) préparé pour
AWS Secrets Manager (prod). Ne modifie rien avant validation.
```

**Décision fin de sprint** : ✅ Go seulement si mandat validé par avocat + fix critiques mergés + tests pytest verts.

---

### Sprint 2 (sem 3-4) — Migration SQLite → Postgres + squelette FastAPI

**Objectif** : abandonner SQLite, passer sur Postgres managé, créer les 3 premiers endpoints FastAPI critiques.

**Livrables** :
- Postgres Neon provisionné (offre free 500 Mo → 25 €/mois quand ça sature)
- Script migration SQLite → Postgres opérationnel (one-shot Python + pandas + SQLAlchemy)
- Alembic initialisé (fin des ALTER TABLE silencieux)
- Squelette FastAPI avec `/auth/login`, `/clients`, `/prospects` (JWT)
- Streamlit `app.py` bascule via `DB_URL` env var — aucune régression fonctionnelle

#### Tâches
- [ ] Provisionner Postgres Neon (compte gratuit, 500 Mo)
- [ ] Chiffrement colonne PII (numéro CNI, IBAN) via `pgcrypto` (`PGP_SYM_ENCRYPT`) — pas dans les migrations 0001/0002
- [ ] Écrire script `migrate_sqlite_to_postgres.py` (~100 lignes, pandas + SQLAlchemy)
- [x] Initialiser Alembic + première migration = état existant — fait (`backend/alembic/`, migration `0001_initial_schema.py` miroir du schéma SQLite)
- [x] Créer arborescence `backend/` (voir section 6.2 du PDF) — fait
- [x] `backend/core/config.py` — Pydantic Settings — fait
- [x] `backend/core/security.py` — JWT, hash mot de passe (PBKDF2 260k conservé), `get_current_user` — fait
- [x] `backend/core/database.py` — SQLAlchemy async, session, engine Postgres — fait (engine créé, mais pas encore de Postgres réel derrière)
- [x] `backend/models/` — modèles SQLAlchemy pour User, Prospect, Client, Contrat, Offre — fait, plus Mandat et Document (anticipé du Sprint 4)
- [x] `backend/routers/auth.py` — login, refresh token, mdp oublié — fait (à vérifier : refresh token / mdp oublié complets)
- [x] `backend/routers/clients.py` + `routers/prospects.py` — fait
- [ ] `frontend-conseiller/api_client.py` — wrapper HTTP vers l'API — non fait (existe déjà côté Streamlit un `api_client.py` legacy vers `crm_api.py`, mais pas vers le nouveau `backend/`)
- [ ] Streamlit `app.py` : basculer les 3 domaines migrés (auth/clients/prospects) sur l'API — non fait, `app.py` tourne toujours en direct sur SQLite via `db.py`

**Prompt Claude Code** :
```
Génère le squelette complet backend/ selon la structure section 6.2 du
IA_Conseil_Roadmap_Complete.pdf. Priorité : main.py, core/config.py,
core/security.py, core/database.py, models/user.py, models/prospect.py,
models/client.py, routers/auth.py. Utilise FastAPI + SQLAlchemy async +
Alembic. Reprends la logique JWT existante de jwt_auth.py. Écris les
migrations Alembic correspondantes. Fournis un requirements.txt à jour.
```

**Décision fin de sprint** : ✅ Go si Streamlit tourne sur Postgres via API pour auth/clients/prospects, aucune régression.

---

### Sprint 3 (sem 5-6) — Portail client MVP (Next.js)

**Objectif** : premier point de contact client hors Streamlit. Login + upload docs + suivi dossier.

**Livrables** :
- Next.js 14 (App Router) déployé sur Vercel
- 3 pages : `/auth/login` (magic link email + code SMS), `/dossier/[id]/documents` (upload guidé), `/dossier/[id]` (timeline suivi)
- S3 Scaleway configuré + chiffré (SSE-KMS pour docs sensibles)
- Endpoints FastAPI correspondants : `POST /documents/upload`, `GET /dossiers/{id}`

#### Tâches
- [ ] `npx create-next-app@latest frontend-client` (App Router, TypeScript, Tailwind)
- [ ] Setup shadcn/ui
- [ ] Compte Scaleway Object Storage + bucket + IAM
- [ ] `backend/routers/documents.py` — upload S3 avec URLs signées, validation MIME/taille
- [ ] `backend/services/kyc_engine.py` (squelette — remplissage sprint 4)
- [ ] Next.js : login magic link (Resend) + code SMS (Twilio/OVH)
- [ ] Next.js : page upload avec drag-and-drop, aperçu instantané
- [ ] Next.js : page timeline dossier (statut, documents, actions)
- [ ] Next.js `/app/api/` — route handlers proxy vers FastAPI
- [ ] CSP stricte (Content Security Policy) côté portail

**Prompt Claude Code** :
```
Crée le squelette frontend-client/ (Next.js 14 App Router, TypeScript,
Tailwind, shadcn/ui). Pages requises : /auth/login (magic link + SMS),
/dossier/[id]/documents (upload drag-and-drop, preview), /dossier/[id]
(timeline). Utilise fetch avec les route handlers /app/api/ comme proxy
vers FastAPI. Ajoute la CSP stricte dans next.config.js. Fournis les
endpoints FastAPI manquants côté backend/routers/documents.py avec URLs
S3 signées (boto3).
```

**Décision fin de sprint** : ✅ Go si un utilisateur test peut se logger, uploader une CNI, voir son dossier.

---

### Sprint 4 (sem 7-8) — Signature électronique + KYC LLM

**Objectif** : signer un mandat en 2 minutes + valider automatiquement les docs uploadés.

**Livrables** :
- Yousign intégré (compte + template mandat + webhook)
- Mandat auto-généré à partir des infos client (PDF)
- Envoi Yousign en 1 clic depuis Streamlit
- Webhook Yousign qui met à jour statut dossier
- `services/kyc_engine.py` — validation LLM Claude Haiku vision (CNI valide, JDD < 3 mois, RIB au bon nom)

#### Tâches
- [ ] Compte Yousign (français, RGPD-natif, eIDAS avancé)
- [ ] Template mandat brouillon Yousign (validation avocat)
- [x] `backend/services/signature_engine.py` — wrapper API Yousign — fait (créer/envoyer/télécharger, API v3), pas encore testé avec un vrai compte
- [x] `backend/routers/webhooks.py` — endpoint `/webhooks/yousign` — fait
- [x] Nouvelle table `mandats` (voir schéma PDF section 6.3) — fait (migration `0002_mandats_documents.py`)
- [ ] Génération PDF mandat à partir des données client (`services/pdf_engine.py` refactoré) — non fait
- [x] `services/kyc_engine.py` : appel Claude Haiku vision, prompt structuré, retour JSON `{type, valide, motif_rejet}` — fait
- [x] Job Celery pour validation async (introduit ici, sera réutilisé partout) — fait (`backend/workers/tasks.py` : `valider_document_kyc`, `envoyer_mandat_signature`, `telecharger_mandat_signe`, avec retry) ; téléchargement/stockage définitif du PDF signé (S3) encore à brancher
- [x] Setup Redis + Celery (`workers/celery_app.py`) — fait
- [ ] UI Streamlit : bouton "Envoyer mandat" + affichage statut signature — non fait

**Prompt Claude Code** :
```
Implémente 3 choses :
1. backend/services/signature_engine.py — wrapper Yousign complet (créer
   demande, envoyer, webhook, télécharger PDF signé). Utilise l'API
   Yousign v3.
2. backend/services/kyc_engine.py — validation KYC via Claude Haiku
   vision. Prompt : "Ce document est-il une CNI valide, un JDD < 3 mois,
   un RIB ? Retourne JSON {type, valide, motif_rejet}". Coût cible :
   ~0.002 € par doc.
3. Setup Celery + Redis pour ces deux tâches en async.
Migrations Alembic pour tables mandats et documents.
```

**Décision fin de sprint** : ✅ Go si mandat signé bout-en-bout en 2 min sur environnement de test.

---

### Sprint 5 (sem 9-10) — Analyse facture LLM

**Objectif** : remplacer le regex actuel de `analyser_facture()` (~60% précision) par un appel LLM (~95%+).

**Livrables** :
- Endpoint `POST /factures/analyze` — PDF → JSON structuré
- `services/facture_analyzer.py` (remplace le regex)
- Tests sur 30 factures réelles de secteurs variés (télécom, énergie)
- Métrique taux de réussite documentée

#### Tâches
- [x] Écrire prompt Claude Haiku structuré (opérateur, prix HT/TTC, data conso, options, engagement, date fin, IBAN) — fait (`backend/services/facture_analyzer.py`, prompt système avec few-shot)
- [x] `backend/routers/factures.py` — endpoint analyze — fait (`POST /factures/analyze`, JWT, `backend/tests/test_factures_router.py`)
- [x] `backend/services/facture_analyzer.py` — appel LLM avec fallback erreur — fait
- [ ] Suite de tests : 30 factures réelles (10 télécom mobile, 10 box/fibre, 10 énergie) — partiel : `backend/tests/test_facture_analyzer.py` avec 3 fixtures synthétiques (mobile/box/énergie) et client Anthropic mocké, pas encore les 30 factures réelles
- [ ] Mesure taux de réussite / précision par champ — non fait
- [x] Migration Streamlit `app.py` : remplacer appel regex par appel API — fait en partie : `app.py` appelle désormais `backend/services/facture_analyzer.py` en Python direct (pas en HTTP — pas besoin de JWT/Postgres pour ça) pour enrichir le repli regex sur opérateur/prix/data ; l'appel HTTP réel (`/factures/analyze`) n'a pas encore de consommateur (attend le portail Next.js ou l'app mobile conseiller)

**Prompt Claude Code** :
```
Écris backend/services/facture_analyzer.py : accepte un chemin PDF, l'envoie
à Claude Haiku (via anthropic SDK), extrait un JSON structuré {operateur,
prix_ht, prix_ttc, data_conso_go, options: [...], engagement_mois,
date_fin_engagement, iban_prelevement}. Fournis le prompt système avec
exemples few-shot. Gère les erreurs proprement. Ajoute pytest avec 3
fixtures de factures anonymisées.
```

**Décision fin de sprint** : ✅ Go si taux de succès > 90% sur les 30 factures test.

---

### Sprint 6 (sem 11-12) — Notifications + 1er dossier bout-en-bout RÉEL

**Objectif** : premier vrai client, du diagnostic à l'envoi fournisseur, sur télécom mobile.

**Livrables** :
- Twilio ou OVH SMS opérationnel
- Templates email transactionnels Resend (mandat signé, docs validés, offre activée)
- Workflow complet testé sur 1 dossier client télécom RÉEL
- Mesures de temps par étape

#### Tâches
- [x] SMS/email — pas de module `sms_engine.py` séparé côté `backend/` : `backend/services/notification_engine.py` (déjà écrit) envoie déjà via OVH/Twilio (SMS) et Resend (email), avec repli gracieux si les clés sont absentes.
- [x] Templates par statut : `backend/services/dossier_notifications.py::TEMPLATES_STATUT` (`docs_demandes`, `mandat_a_signer`, `mandat_signe`, `soumis_fournisseur`, `actif`) — fait le 2026-07-21.
- [x] Machine à états dossier — table `dossiers` (statuts : initie | docs_demandes | docs_recus | mandat_a_signer | mandat_signe | soumis_fournisseur | en_activation | actif | facture | echec | annule), colonnes `date_derniere_transition`/`derniere_relance_envoyee_le` ajoutées (migration `0005`).
- [x] Trigger automatique notifications à chaque transition d'état — branché dans `POST /dossiers/{id}/transition` et sur l'auto-transition déclenchée par le webhook Yousign (`backend/workers/tasks.py::_telecharger_mandat_signe`).
- [x] Relance automatique si dossier stagnant (hors scope initial) — `backend/workers/tasks.py::relancer_dossiers_stagnants`, seuils par statut (`SEUILS_JOURS_PAR_STATUT`), planifiée quotidiennement (`celery_app.beat_schedule`, 8h Europe/Paris).
- [ ] Recrutement 1 vrai client télécom (bouche-à-oreille)
- [ ] Suivi dossier bout-en-bout avec mesure temps par étape

**Prompt Claude Code** :
```
1. Crée backend/services/sms_engine.py (interface commune, backend Twilio
   ou OVH configurable).
2. Crée les templates email Resend dans backend/services/email_engine.py
   (refactorisé). Templates : mandat_envoye, mandat_signe, docs_valides,
   offre_activee. Utilise MJML ou HTML propre.
3. Implémente la machine à états dossier dans backend/services/
   dossier_state_machine.py. Chaque transition déclenche la notification
   correspondante.
4. Migration Alembic pour les colonnes de statut.
```

**Décision fin de sprint** : 🎯 **JALON MAJEUR** — 1 vrai client traité, temps mesuré, décision passage Phase 2.

---

<a id="phase-2"></a>
## PHASE 2 — Automatisation télécom + énergie (mois 4 à 6)

### Sprint 7 (sem 13-14) — Contrats apporteurs télécom
- [ ] Signer avec 2 opérateurs minimum (Bouygues, SFR, YouPrice, Prixtel)
- [ ] Adapters de soumission dans `services/soumission_engine.py` — un module par fournisseur
- [ ] Formulaire diagnostic Streamlit adapté avec mode "Pro" (SIRET, nb lignes, fibre, VoIP)

### Sprint 8 (sem 15-16) — Stripe + facturation client
- [ ] Compte Stripe Billing + configuration SEPA Direct Debit
- [ ] Mandat SEPA signé en même temps que le mandat de représentation (Yousign)
- [ ] Subscription Stripe avec durée limitée (6-12 mois selon barème)
- [ ] Webhooks Stripe : paiement OK, impayé, relance auto
- [ ] Dashboard client avec suivi paiements

### Sprint 9 (sem 17-18) — Extension énergie B2C
- [ ] Contrats Ekwateur + TotalEnergies
- [ ] Adapter soumission énergie (`services/soumission_engine.py`)
- [ ] Template facture énergie
- [ ] Extension workflow (statuts spécifiques : demande RIB frns, relève index)

### Sprint 10 (sem 19-20) — Extension B2B télécom (pro)
- [ ] Formulaire diagnostic Pro (SIRET, multi-lignes, VoIP, fibre pro)
- [ ] Contrats Bouygues Business Partners + SFR Business Distribution
- [ ] Deal size cible ~500-1500 € de commission

### Sprint 11 (sem 21-22) — Veille tarifaire
- [ ] Scraper Playwright headless : Ariase, Selectra, comparateur-offres.energie-info.fr
- [ ] Stockage `veille_snapshots` (JSONB)
- [ ] Alertes conseiller si baisse > 10% sur un fournisseur
- [ ] Respect robots.txt + rotation IP si nécessaire (ScraperAPI ou Bright Data ~50-100 €/mois)
- [ ] Cron quotidien MAJ catalogue

### Sprint 12 (sem 23-24) — Retention + upsell Gestionnaire perso
- [ ] Landing page offre "Gestionnaire perso" 4,90 €/mois
- [ ] Upsell auto post-conversion (email + notif portail J+7 après activation)
- [ ] Table `abonnements` + Subscription Stripe récurrente
- [ ] Mesure taux de conversion Gestionnaire

**Décision fin Phase 2** : ✅ Go si 50 dossiers/mois traités avec revenu > coûts.

---

<a id="phase-3"></a>
## PHASE 3 — Scale + verticales B2B (mois 7 à 9)

### Sprint 13 (sem 25-26) — Alarme / télésurveillance
- [ ] Partenariats Verisure ou EPS
- [ ] Cross-sell auto sur clients pros existants (commissions 150-500 € / contrat)
- [ ] Cycle vente long : lead qualifié → VRP installation

### Sprint 14 (sem 27-28) — Terminal de paiement (TPE)
- [ ] Partenariats SumUp / Zettle / myPOS
- [ ] Formulaire qualification lead pro
- [ ] Commissions 100-300 € + rétrocommission sur volume

### Sprint 15 (sem 29-30) — Alerte renouvellement client
- [ ] Job cron quotidien : comparer contrats actifs de chaque client au catalogue à jour
- [ ] Si delta > 10 €/mois → tâche rappel conseiller
- [ ] Générateur de commissions RÉCURRENTES sans acquisition

### Sprint 16 (sem 31-32) — Énergie Pro (B2B)
- [ ] Contrats Ekwateur Pro + TotalEnergies Pro
- [ ] Workflow B2B énergie (contrat vs particulier : bail commercial, PDL)
- [ ] Commissions énormes : 200-800 € / contrat

### Sprint 17 (sem 33-34) — Chatbot IA pré-diagnostic
- [ ] Widget React embarqué sur homepage
- [ ] Backend FastAPI + LLM Claude avec function calling
- [ ] 5-8 questions → pré-diag gratuit → génération lead qualifié
- [ ] Mesure conversion visiteurs → leads

### Sprint 18 (sem 35-36) — Dashboard commissions + réconciliation
- [ ] Intégration Bridge ou Powens (API bancaire)
- [ ] Matching auto commissions attendues vs reçues (fuzzy match libellé + montant)
- [ ] Alertes si commissions manquantes à J+90
- [ ] Récupération estimée : 10-20% de CA "perdu"

**Décision fin Phase 3** : ✅ Go si 150-200 dossiers/mois + MRR Gestionnaire > 2 000 €/mois.

---

<a id="phase-4"></a>
## PHASE 4 — ORIAS + Assurance (mois 10 à 12)

### Sprint 19-20 (sem 37-40) — Formation IAS + immatriculation
- [ ] Formation IAS niveau 1 (150h e-learning, ~1 500 €)
- [ ] Immatriculation ORIAS Courtier (COA) ou Mandataire (MIA) (~30 €/an)
- [ ] RC pro spécifique assurance (~500 €/an)

### Sprint 21 (sem 41-42) — Grossistes assurance
- [ ] Contrats April + Néoliane (grossistes)
- [ ] Intégration API partenaires
- [ ] Workflow spécifique assurance (questionnaire médical, périodes carence)

### Sprint 22 (sem 43-44) — Mutuelle santé (B2C + collective TPE)
- [ ] Catalogue offres santé
- [ ] Campagne marketing dédiée
- [ ] Cross-sell aux clients TPE existants

### Sprint 23 (sem 45-46) — Auto + habitation
- [ ] Extension auto/habitation
- [ ] Cross-sell : client télécom + énergie + alarme = cible naturelle pour assurance habitation

### Sprint 24 (sem 47-48) — Bilan année 1 + roadmap année 2
- [ ] Revue complète KPIs
- [ ] Ajustements stratégiques
- [ ] Préparation photovoltaïque (partenariat RGE) + SaaS B2B (Microsoft CSP / Google Workspace Partner)

---

<a id="chantiers-transverses"></a>
## Chantiers transverses (à faire en continu)

### Refactor du code existant (dette technique — cf. section 10 du PDF)

**À corriger EN PRIORITÉ (dès Phase 1)** :
- [x] **CRITIQUE** — Mots de passe SMTP en session_state → env vars (S1)
- [x] **CRITIQUE** — Rate limiting login (S1)
- [ ] **CRITIQUE** — Migration DB SQLite → Postgres + chiffrement colonne PII (S2) — squelette Postgres/Alembic prêt côté `backend/`, mais Streamlit tourne toujours sur SQLite et le chiffrement PII n'est pas fait
- [ ] **HAUTE** — Recherche client `str(row.to_dict())` inefficient + fuite données → filtrage par colonnes indexées (S2)
- [ ] **HAUTE** — `generer_ref()` peut générer doublons en concurrence → séquence Postgres ou UUID (S2)
- [x] **HAUTE** — `analyser_facture()` regex → LLM (S5) — fait pour les champs opérateur/prix/data (`app.py` appelle `backend/services/facture_analyzer.py` en complément du regex, cf. Sprint 5) ; l'identité client (cp/ville/prénom/nom/tél/email) reste extraite par regex, non couverte par le service LLM
- [x] **MOYENNE** — 0 tests unitaires → suite pytest > 60% (S1 progressif) — 11 fichiers de tests côté `src/`, à mesurer précisément la couverture réelle
- [ ] **MOYENNE** — `app.py` monolithique 1500 lignes → découpe modules (S2-S6)
- [x] **MOYENNE** — Table `documents` inexistante → créer (S2/S4) — fait côté `backend/` (migration `0002`), pas encore côté SQLite/Streamlit
- [x] **MOYENNE** — Workflow / statut dossier impossible à tracker → table `dossiers` + machine à états (S6) — fait, avec historique horodaté (transitions + notes manuelles + relances auto) affiché au conseiller (`src/app.py`)
- [ ] **BASSE** — SMTP en clair sans retry → Celery + Resend/SendGrid (S4)
- [x] **BASSE** — Pas d'API → FastAPI (S2) — squelette FastAPI `backend/` créé (auth/clients/prospects/webhooks), à compléter et à connecter

### Sécurité (à durcir sans discontinuer)
- [ ] MFA obligatoire rôles Admin (TOTP app authenticator)
- [ ] Session expirée 30 min inactivité (JWT access 15 min + refresh 7 jours)
- [ ] Logs consultation données sensibles (`historique_actions`)
- [ ] Suppression sécurisée S3 (Object Lock + shred, pas juste marquage)
- [ ] Chiffrement backup + test restauration mensuel
- [ ] Chiffrement colonne pgcrypto pour CNI, IBAN

### RGPD (parcours conforme dès J1)
- [ ] Mention info à chaque étape (formulaire, prospect, upload docs, mandat, souscription, résiliation)
- [ ] Bases légales identifiées par traitement
- [ ] DPA signés avec chaque prestataire (hébergeur, Yousign, OCR)
- [ ] Endpoint API + procédure exercice des droits (accès, effacement, portabilité)
- [ ] Politique conservation (3 ans après fin relation, puis effacement)
- [ ] DPO externe recommandé dès 200+ clients actifs (~150 €/mois)

### Transparence rémunération (contrôle DGCCRF prioritaire)
- [ ] À chaque proposition : mention écrite du montant commission fournisseur + montant participation client (€ + %)
- [ ] Démonstration objectivité : présenter aussi offres de fournisseurs commissionnant moins
- [ ] Barème "% économies" reformulé : "vous gardez 100% des économies, vous nous versez X € les 6 premiers mois" (jamais "je prends X%")

---

<a id="kpis"></a>
## KPIs à suivre dès le 1er dossier

À mettre dans dashboard Streamlit "Pilotage" (Admin only) :

| Catégorie | KPI | Cible |
|---|---|---|
| Acquisition | CPL (Coût par lead) | < 30 € |
| Acquisition | Conv. lead → RDV | > 40 % |
| Acquisition | Conv. RDV → signature | > 30 % |
| Acquisition | CAC | < 200 € |
| Revenus | Commission moyenne / dossier | > 80 € |
| Revenus | MRR Gestionnaire | Cumulatif |
| Revenus | LTV 24 mois | > 400 € |
| Revenus | Ratio LTV/CAC | > 3 |
| Opérations | Durée moyenne dossier | < 14 j |
| Opérations | Temps conseiller / dossier | < 90 min |
| Opérations | Taux automatisation | > 70 % |
| Rétention | Churn abonnement mensuel | < 3 % |
| Financier | Commissions récupérées J+90 | > 95 % |
| Client | NPS | > 50 |

**Setup** : materialized views Postgres rafraîchies chaque nuit + alertes email si franchissement seuil.

---

<a id="budget"></a>
## Budget infrastructure attendu

### À 50 dossiers/mois (démarrage, mois 1-3)
**~80 à 170 €/mois** (Neon free, Scaleway, Vercel, Fly.io, Yousign, SMS, LLM, Sentry, OVH)

### À 200 dossiers/mois (régime établi, mois 6-12)
**~560 à 880 €/mois** (Postgres Scale, S3, FastAPI scaled, Yousign 200, Bridge API, Stripe frais, Sentry Business)

Ratio infra/CA @ 30 k€/mois = **2 à 3%**. Sain.

---

<a id="décisions"></a>
## Décisions en attente de TA réponse

Pour que je (Claude Code) puisse démarrer le Sprint 1 sans blocage, il me faut ta décision sur :

1. **Avocat** : tu as déjà un contact ou tu veux que je te propose une short-list de cabinets spécialisés droit du numérique + consommation à Paris/région ?

2. **Ordre univers confirmé ?** — Le PDF propose Télécom (M1-3) → Énergie (M4-6) → Assurance/ORIAS (M10-12), avec verticales pro en parallèle. Tu veux qu'on modifie l'ordre ?

3. **Budget dev perso** : combien d'heures/semaine tu peux mettre + budget prestation externe éventuel (ex : dev frontend pour accélérer le portail Next.js) ?

4. **Statut juridique actuel** : la SAS est déjà créée ou c'est encore à faire ?

5. **Comptes déjà ouverts** : lesquels des 8 outils critiques (Neon, Scaleway, Vercel, Yousign, Anthropic, Stripe, Resend, Twilio) sont déjà en place ?

6. **Priorité Sprint 1** : on attaque en parallèle juridique + sécurisation code, ou tu préfères d'abord finaliser le juridique et ensuite lancer le code ?

7. **Test client réel Sprint 6** : tu as déjà un prospect / bouche-à-oreille identifié pour tester le 1er dossier bout-en-bout, ou il faut aussi prévoir l'acquisition ?

Réponds à ces 7 points et je te génère immédiatement le **plan de travail Sprint 1** détaillé jour par jour + le premier prompt Claude Code prêt à lancer.

---

## Comment j'attaquerai avec toi (méthode Claude Code)

À chaque début de sprint :
1. Tu ouvres Claude Code, tu me colles la section du sprint concerné
2. Je te propose un **plan d'attaque détaillé** avec ordre des tâches
3. On code par petits blocs (1 fichier = 1 revue = 1 commit)
4. À chaque livrable, tests + démo Streamlit
5. Fin de sprint : je te rédige la **rétrospective** (ce qui a marché, dette accumulée, décision Go/No-Go)

**Règle** : jamais de "je fais tout d'un coup". On avance par incréments testables.

> « Ne cherche pas à tout construire seul en 6 mois. Concentre-toi sur ce qui fait la différence : le triangle multi-univers × full-service × rémunération alignée. Le reste, on l'automatise pour que ton équipe reste petite et rentable. »
