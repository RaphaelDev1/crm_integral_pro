# Guide de lancement — IA Conseil

> Référence opérationnelle : comment configurer, lancer, tester et vérifier chaque brique du projet
> (Streamlit conseiller, backend FastAPI, Celery, portail client Next.js, Docker).
> Écrit après audit du code réel le 2026-07-24 — voir `SETUP_STATUS.md` et `ROADMAP_EXECUTION.md`
> pour l'avancement fonctionnel détaillé par sprint/chantier.

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
  - Optionnels selon les fonctionnalités testées : `S3_*` (upload documents), `YOUSIGN_API_KEY` (signature), `AR24_API_KEY` (LRE démarches), `STRIPE_*`, `RESEND_*`/`TWILIO_*`/`OVH_*` (notifications). Sans ces clés, le code dégrade proprement (pas de crash, juste la fonctionnalité désactivée).
- Installer les dépendances :
  ```powershell
  pip install -r backend/requirements-dev.txt
  pip install -r src/requirements-dev.txt
  cd frontend-portail && npm install && cd ..
  ```

## 1. Appliquer les migrations Alembic (à faire avant tout, obligatoire)

```powershell
python -m alembic upgrade head
python -m alembic current   # doit afficher "0008 (head)"
```
Sans cette étape, les tables des derniers chantiers (`demarches`, `tokens_publics`) n'existent pas sur Postgres.

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

# Portail client Next.js
cd frontend-portail
npm run dev
```

Vérifications rapides :
- `http://localhost:8000/health` → `200 OK`
- `http://localhost:8000/docs` → Swagger avec tous les routers (auth, clients, prospects, dossiers, demarches, portail_public, factures, honoraires, webhooks)
- `http://localhost:8501` → Streamlit se charge, login admin
- `http://localhost:3000` → landing du portail

## 3. Ou tout lancer via Docker Compose

```powershell
docker compose up --build
# + Postgres local si besoin (sinon backend/.env pointe sur Neon) :
docker compose --profile local-db up --build
```
Services lancés : redis, backend (`:8000`), celery-worker, celery-beat, flower (`:5555`), streamlit (`:8501`).
Le portail Next.js n'est pas dans le compose — le lancer à part avec `npm run dev`.

Vérif : `http://localhost:5555` (Flower) doit montrer le worker actif et les tâches planifiées
(`relancer_dossiers_stagnants`, `verifier_accuses_lre_en_attente`).

## 4. Lancer les tests

```powershell
cd src
python -m pytest -q          # 194 tests attendus verts

cd ..
python -m pytest backend/tests -q

ruff check backend           # lint (scope backend/ uniquement, voir pyproject.toml)
```

> **Connu au 2026-07-24** : `backend/tests/test_facture_analyzer.py::test_sans_cle_api` et
> `::test_erreur_api_anthropic_est_convertie` échouent — `facture_analyzer.py` dégrade proprement
> au lieu de lever `FactureAnalyzerError`, les tests n'ont pas été mis à jour en conséquence.

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

## 6. État des blocages externes (comptes à créer)

Aucune fonctionnalité ne crashe si ces comptes manquent — dégradation propre — mais restent bloqués :
- **S3 (Scaleway)** : upload de documents.
- **Yousign** : signature électronique.
- **AR24** : envoi LRE des démarches.
- **Stripe** : facturation/abonnements.
- **Resend / Twilio / OVH** : email et SMS transactionnels.

Voir `SETUP_STATUS.md` pour le détail des étapes manuelles par compte.
