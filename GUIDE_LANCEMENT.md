# Guide de lancement — IA Conseil

> Référence opérationnelle : comment configurer, lancer, tester et vérifier chaque brique du projet
> (Streamlit conseiller — en cours d'extinction, voir `frontend-conseiller/LANCEMENT.md` pour son
> remplaçant Next.js —, backend FastAPI, Celery, portail client Next.js, Docker).
> Écrit après audit du code réel le 2026-07-24, mis à jour le 2026-08-26 (landing publique
> `/economiser`, capture de leads, Dashboard UTM) — voir `SETUP_STATUS.md` et
> `ROADMAP_EXECUTION.md` pour l'avancement fonctionnel détaillé par sprint/chantier.

---

## 0. Pré-requis & configuration

- Python 3.11 (venv `.venv` déjà présent), Node.js (pour `frontend-portail/`), Docker (optionnel).
- Copier les fichiers d'exemple si pas déjà fait :
  ```powershell
  Copy-Item src/.env.example src/.env
  Copy-Item backend/.env.example backend/.env
  Copy-Item frontend-portail/.env.example frontend-portail/.env.local
  ```
- Remplir au minimum :
  - `backend/.env` : `DATABASE_URL` (Neon Postgres), `ANTHROPIC_API_KEY`, `REDIS_URL`, `CRM_API_SECRET`.
  - `src/.env` : `ANTHROPIC_API_KEY` (nécessaire pour l'agent d'audit et le chatbot en Streamlit), `CRM_API_SECRET`.
  - Optionnels selon les fonctionnalités testées : `S3_*` (upload documents), `YOUSIGN_API_KEY` (signature), `AR24_API_KEY` (LRE démarches), `STRIPE_*`, `RESEND_*`/`TWILIO_*`/`OVH_*` (notifications), `TURNSTILE_SECRET_KEY` (captcha landing), `ELIGIBILITE_FIBRE_API_URL` (déjà pré-rempli avec la valeur publique par défaut). Sans ces clés, le code dégrade proprement (pas de crash, juste la fonctionnalité désactivée).
  - `RATE_LIMIT_STORAGE_URI` (déjà pré-rempli `memory://`) : suffisant en dev local (un seul process) pour le rate limiting de la landing publique `/economiser` — pas besoin de Redis pour ça, seulement pour Celery.
  - `frontend-portail/.env.local` : `NEXT_PUBLIC_API_URL` + `BACKEND_URL` (déjà pré-remplis en local). Optionnels : `NEXT_PUBLIC_CALCOM_LINK` (prise de rendez-vous étape 4 landing), `NEXT_PUBLIC_LANDING_VARIANT` (A/B test), pixels `NEXT_PUBLIC_META_PIXEL_ID`/`NEXT_PUBLIC_TIKTOK_PIXEL_ID`/`NEXT_PUBLIC_GA_MEASUREMENT_ID`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY` (doit rester cohérent avec `TURNSTILE_SECRET_KEY` côté backend). Vides = fonctionnalités correspondantes masquées/désactivées, pas de crash.
- Installer les dépendances :
  ```powershell
  pip install -r backend/requirements-dev.txt
  pip install -r src/requirements-dev.txt
  cd frontend-conseiller && npm install && cd ..
  cd frontend-portail && npm install && cd ..
  ```

## 0bis. Démarrage rapide — Conseiller + Portail (prêt à l'emploi)

Une fois §0 et §1 faits une première fois (`.env` remplis, `npm install` fait dans
`frontend-conseiller/` et `frontend-portail/`, migrations appliquées), lance les 4 services
(Redis, backend `:8000`, conseiller `:3001`, portail `:3000`) en une seule commande :

**Depuis PowerShell** (ouvre 4 fenêtres séparées) :
```powershell
.\lancer-app.ps1
```

**Depuis VSCode** : `Ctrl+Shift+P` → *Tasks: Run Task* → **🚀 Lancer tout (conseiller + portail)**
(définit 4 terminaux dédiés dans le panneau Terminal — `.vscode/tasks.json`).

Pour arrêter : fermer chaque fenêtre/terminal (ou `Ctrl+C` dedans).

## 1. Appliquer les migrations Alembic (à faire avant tout, obligatoire)

```powershell
python -m alembic upgrade head
python -m alembic current   # doit afficher "0029 (head)"
```
Sans cette étape, les tables des derniers chantiers (`demarches`, `tokens_publics`, `veille`,
`catalogue_sources`/`offres_staging`, `leads_capture`, `campagnes_cout`, `touchpoints`, etc.)
n'existent pas sur Postgres.

> ⚠️ Migrations 0027 à 0029 ajoutées le 2026-08-26 (`leads_capture` : table des leads landing
> publique ; `leads_enrichissements` : colonnes détection FAI/éligibilité fibre/vérification
> téléphone sur le lead ; `utm_dashboard_attribution` : `campagnes_cout` + `touchpoints` pour le
> Dashboard UTM conseiller) — vérifier qu'elles sont appliquées avant de tester la landing
> `/economiser` ou `/dashboard/utm`.

## 2. Lancer chaque brique en local (sans Docker)

Dans des terminaux séparés (venv activé) :

```powershell
# Backend FastAPI
uvicorn backend.main:app --reload --port 8000

# Redis (si pas installé localement)
docker run -p 6379:6379 redis:7-alpine

# Celery worker + beat (relances auto, ingestion planifiée, envoi LRE)
celery -A backend.workers.celery_app worker --loglevel=info --pool=solo
celery -A backend.workers.celery_app beat --loglevel=info

# Streamlit conseiller
cd src
streamlit run app.py

# Portail client Next.js (voir aussi §3 pour le lancer via Docker à la place)
cd frontend-portail
npm run dev
```

Vérifications rapides :
- `http://localhost:8000/health` → `200 OK`
- `http://localhost:8000/docs` → Swagger avec tous les routers (auth, clients, prospects, dossiers,
  demarches, portail_public, factures, honoraires, webhooks, `leads_public` (formulaire landing
  publique), `dashboard_utm` (attribution marketing))
- `http://localhost:8501` → Streamlit se charge, login admin
- `http://localhost:3001` → frontend-conseiller, dont `/dashboard/utm` (Dashboard UTM)
- `http://localhost:3000` → landing du portail, dont `/economiser` (formulaire de capture de lead)

## 3. Ou tout lancer via Docker Compose

```powershell
docker compose up --build
# + Postgres local si besoin (sinon backend/.env pointe sur Neon) :
docker compose --profile local-db up --build
```
Services lancés : redis, backend (`:8000`), celery-worker, celery-beat, flower (`:5555`), streamlit
(`:8501`), **et le portail client Next.js (`frontend-portail`, `:3000`, hot-reload — `npm run dev`
monté en volume dans le conteneur, pas un build de prod)**. `frontend-conseiller` reste hors compose
(lancé via `npm run dev`, voir `frontend-conseiller/LANCEMENT.md`).

Pour ne lancer que le portail (les autres briques tournant déjà en local, sans Docker) :
```powershell
docker compose up frontend-portail
```
> Après un `npm install` dans `frontend-portail/` (nouvelle dépendance) : reconstruire l'image
> avec `docker compose build frontend-portail` avant de relancer — le conteneur garde sinon
> l'ancien `node_modules`.

Vérif : `http://localhost:5555` (Flower) doit montrer le worker actif et les tâches planifiées
(`relancer_dossiers_stagnants`, `verifier_accuses_lre_en_attente`) ; `http://localhost:3000` →
landing du portail. C'est ce port (`:3000`) que pointent les liens de collecte de documents envoyés
aux prospects/clients (`PORTAIL_CLIENT_BASE_URL` dans `backend/.env`, défaut
`http://localhost:3000`) — sans ce service lancé, ces liens renvoient `ERR_CONNECTION_RESET`.

## 4. Lancer les tests

```powershell
cd src
python -m pytest -q          # 203 tests attendus verts

cd ..
python -m pytest backend/tests -q   # 221 tests attendus verts

ruff check backend           # lint (scope backend/ uniquement, voir pyproject.toml)
```

> ✅ Corrigé le 2026-07-24 : `test_facture_analyzer.py` distinguait mal le comportement volontaire
> de `facture_analyzer.py` (dégradation propre hors production, `FactureAnalyzerError` uniquement
> en production — `settings.is_production`). Les tests couvrent maintenant explicitement les deux
> cas (`*_leve_en_production` / `*_degrade_proprement_hors_production`).

## 5. Vérifier concrètement chaque chantier d'automatisation

**Chantier 1 — Catalogue auto-alimenté**
1. Redémarrer Streamlit une fois (`initialiser_bdd()` crée `catalogue_sources`/`offres_staging` si absentes).
2. Admin > 📚 Catalogue > 🔎 Sources à ingérer → ajouter une source réelle (page tarifs officielle).
3. Bouton « 🔎 Ingérer maintenant » → vérifier que le résultat tombe dans « 🆕 Offres détectées », jamais directement dans le catalogue actif.

**Chantier 2 — Agent d'audit** (nécessite `ANTHROPIC_API_KEY` dans `src/.env`)
```powershell
python scripts/eval_audit.py
```
Donne un score réel X/10 sur les 10 cas de `src/tests/cas_audit_eval/` (coûte quelques appels API réels, script volontairement exclu de la CI).

**Chantier 3 — Démarches** (une fois les migrations appliquées)
Via Swagger (`:8000/docs`) : `POST /clients` → `POST /dossiers` → signer le mandat → `POST /demarches`.
Vérifier le refus si le mandat n'est pas signé, et la génération PDF si signé.

**Chantier 4 — Industrialisation**
`docker compose up`, observer Flower, provoquer une exception pour vérifier qu'elle remonte dans Sentry (si un DSN est configuré).

**Chantier 5 — Landing publique `/economiser` + attribution UTM** (nécessite les migrations
0027-0029, backend + portail + conseiller lancés)
1. Ouvrir `http://localhost:3000/economiser?utm_source=test&utm_medium=cpc&utm_campaign=demo`
   → l'attribution UTM est capturée côté client (`lib/attribution.ts`) et transmise à la
   soumission du formulaire.
2. Dérouler les 4 étapes du formulaire (adresse avec autocomplétion, opérateur pré-rempli par
   détection FAI, captcha invisible à l'étape 3, bannière éligibilité fibre + bouton Cal.com à
   l'étape 4 si les clés correspondantes sont configurées, sinon masqués proprement).
3. Soumettre → `POST /leads/capture` (rate-limité par IP, voir `backend/core/rate_limit.py`) crée
   le lead, notifie Slack si `SLACK_WEBHOOK_URL` est configuré, et programme l'email J+1 via Celery
   (nécessite worker + beat lancés, `-SansCelery` désactive ce dernier point).
4. Vérifier le lien de désabonnement `GET /leads/desabonner/{ref}` renvoyé dans l'email (si
   `RESEND_API_KEY` configuré).
5. Dans `frontend-conseiller`, ouvrir `/dashboard/utm` → vérifier que le lead créé à l'étape 3
   apparaît dans le tunnel et l'attribution par source/campagne (`GET /dashboard/utm-tunnel`,
   `/dashboard/attribution`, `/dashboard/couts-campagne`).

Voir `docs/RETARGETING_META_TIKTOK.md` (configuration des pixels/audiences) et
`docs/REGISTRE_TRAITEMENTS_CNIL.md` (registre RGPD de ce traitement) pour le contexte métier de ce
chantier.

## 6. État des blocages externes (comptes à créer)

Aucune fonctionnalité ne crashe si ces comptes manquent — dégradation propre — mais restent bloqués :
- **S3 (Scaleway)** : upload de documents.
- **Yousign** : signature électronique.
- **AR24** : envoi LRE des démarches.
- **Stripe** : facturation/abonnements.
- **Resend / Twilio / OVH** : email et SMS transactionnels.
- **Cloudflare Turnstile** : captcha du formulaire landing `/economiser` (sans clé, le formulaire
  fonctionne sans vérification anti-bot).
- **Twilio Lookup** : vérification de la validité des numéros de téléphone des leads landing
  (réutilise `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`, indépendant de `SMS_PROVIDER`).
- **Cal.com** : prise de rendez-vous directe à l'étape 4 de la landing (sans `NEXT_PUBLIC_CALCOM_LINK`, le bouton est masqué).
- **Pixels Meta / TikTok / GA4** : retargeting des visiteurs de la landing (sans ID configuré, aucun pixel n'est chargé).

Voir `SETUP_STATUS.md` pour le détail des étapes manuelles par compte.
