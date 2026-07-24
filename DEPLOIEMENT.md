# Déploiement — IA Conseil

Ce document est **uniquement une procédure** : aucun compte tiers n'a été créé, aucun déploiement
réel n'a été effectué à ce jour. Même logique que `SETUP_STATUS.md` pour les comptes externes —
à faire manuellement, dans l'ordre ci-dessous. Prérequis local : Docker (voir `docker-compose.yml`
pour le dev, `backend/Dockerfile` / `src/Dockerfile` / `frontend-portail/Dockerfile` pour la prod).

---

## 1. Backend + Celery (worker/beat) — Fly.io (recommandé)

Choisi ici en priorité (bon support de process séparés `web`/`worker`/`beat` via un seul `fly.toml`,
HTTPS automatique, facturé au conteneur). Alternatives rapides en fin de section.

### 1.1 Compte et CLI

```bash
# https://fly.io/docs/hands-on/install-flyctl/
fly auth signup   # ou fly auth login si déjà un compte
fly launch --no-deploy --dockerfile backend/Dockerfile
```
`fly launch` génère un `fly.toml` à la racine — l'adapter avec le contenu ci-dessous (3 process
distincts sur la même image, comme dans `docker-compose.yml`).

### 1.2 `fly.toml` (exemple)

```toml
app = "ia-conseil-backend"
primary_region = "cdg"  # Paris

[build]
  dockerfile = "backend/Dockerfile"

[processes]
  app = "uvicorn backend.main:app --host 0.0.0.0 --port 8000"
  worker = "celery -A backend.workers.celery_app worker --loglevel=info"
  beat = "celery -A backend.workers.celery_app beat --loglevel=info"

[http_service]
  internal_port = 8000
  force_https = true
  processes = ["app"]
  [[http_service.checks]]
    path = "/health"
    interval = "30s"
    timeout = "5s"

[[vm]]
  processes = ["app"]
  memory = "512mb"

[[vm]]
  processes = ["worker", "beat"]
  memory = "256mb"
```

### 1.3 Secrets (jamais dans `fly.toml`, ni dans l'image)

```bash
fly secrets set \
  DATABASE_URL="postgresql+asyncpg://...@...neon.tech/ia_conseil?ssl=require" \
  CRM_API_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  ANTHROPIC_API_KEY="sk-ant-..." \
  YOUSIGN_API_KEY="..." \
  YOUSIGN_WEBHOOK_SECRET="..." \
  REDIS_URL="rediss://...upstash.io:6379" \
  PORTAIL_CLIENT_BASE_URL="https://portail.iaconseil.fr" \
  S3_BUCKET="..." S3_ACCESS_KEY_ID="..." S3_SECRET_ACCESS_KEY="..." \
  SENTRY_DSN="https://...@...ingest.sentry.io/..." \
  APP_ENV=production
```
Toutes ces clés existent déjà dans `backend/.env.example` — aucun changement de code n'est requis
côté `backend/core/config.py` (Pydantic Settings lit indifféremment `.env` en dev ou de vraies
variables d'environnement en prod, `fly secrets` les injecte de la même façon).

### 1.4 Migrations et déploiement

```bash
fly deploy
fly ssh console -C "alembic upgrade head"   # une fois, après le premier déploiement
```

### 1.5 Alternatives

- **Railway** : plus simple à prendre en main (déploiement par UI ou push Git, un service par
  process — `web`, `worker`, `beat` — chacun avec la même image `backend/Dockerfile` et sa propre
  commande de démarrage), légèrement plus cher à l'échelle.
- **Scaleway Containers** : cohérent avec le S3 Scaleway déjà utilisé (`backend/services/storage_engine.py`),
  mais moins taillé nativement pour des workers Celery long-running (pensé pour du scale-to-zero
  HTTP) — préférer Fly.io/Railway pour `worker`/`beat`.

---

## 2. Portail client Next.js — Vercel

1. Connecter le repo sur [vercel.com](https://vercel.com), **Root Directory** = `frontend-portail`.
2. Variables d'environnement (Project Settings → Environment Variables) :
   - `NEXT_PUBLIC_API_URL` = URL publique du backend (ex. `https://ia-conseil-backend.fly.dev`)
   - `NEXT_PUBLIC_SENTRY_DSN` = DSN du projet Sentry dédié au portail
3. Vercel détecte Next.js automatiquement (`next build`) — le `frontend-portail/Dockerfile` créé
   pour ce projet sert plutôt à un déploiement conteneur alternatif (Fly.io/Scaleway), pas requis
   sur Vercel.
4. HTTPS automatique, rien à configurer.

---

## 3. Streamlit conseiller

Deux options, selon si l'accès doit être ouvert à plusieurs conseillers ou usage solo :

- **Streamlit Community Cloud** (privé) : le plus simple, connecter le repo, `Main file path` =
  `src/app.py`, variables d'environnement dans les "Secrets" de l'app (mêmes clés que `src/.env.example`).
  ⚠️ Playwright (souscription assistée, veille prix, catalogue) ne fonctionne pas sur Community
  Cloud (pas d'accès navigateur headless) — ces fonctionnalités resteraient réservées à un usage
  local ou au conteneur ci-dessous.
- **Même hébergeur conteneur que le backend** (Fly.io/Railway), avec `src/Dockerfile` (image
  complète Playwright+Chromium) — **derrière une authentification supplémentaire au niveau de la
  plateforme** (ex. Fly.io proxy avec Basic Auth, ou un reverse-proxy dédié) puisque Streamlit lui
  seul n'expose que l'auth applicative déjà en place (`src/auth.py`), pas un contrôle d'accès réseau.

---

## 4. Postgres — Neon (déjà provisionné)

- **PITR / branching** : Neon Console → le projet → activer le "Point-in-time restore" (durée de
  rétention selon le plan) et créer une **branche** de test avant toute migration risquée.
- **Test de restauration** (à faire une fois, puis mensuellement — item roadmap) :
  1. Neon Console → Branches → créer une branche depuis un point dans le temps récent.
  2. Récupérer la `DATABASE_URL` de cette branche, la mettre temporairement dans un `.env` de test.
  3. `alembic current` puis quelques requêtes de lecture pour vérifier l'intégrité des données.
  4. Supprimer la branche de test une fois vérifié.

## 5. Redis — Upstash

Créer une base Upstash Redis (région proche de `cdg`/Fly.io), copier l'URL `rediss://...` (TLS)
dans `REDIS_URL` (secret Fly, voir §1.3) — aucun changement de code, `backend/core/config.py`
utilise déjà `redis_url` tel quel pour Celery et le broker.

## 6. HTTPS/TLS

Automatique sur les 3 plateformes ci-dessus (Fly.io, Vercel, Streamlit Community Cloud) — rien à
coder ni à configurer côté certificats.

## 7. Stockage S3 (Scaleway Object Storage)

- **Versioning** : Console Scaleway → bucket → Settings → activer le versioning.
- **Object Lock** sur les documents sensibles (CNI, RIB, mandats signés) : à activer **à la
  création du bucket** (ne peut pas être activé après coup sur un bucket existant) — si le bucket
  actuel n'a pas été créé avec Object Lock, en créer un second dédié aux documents les plus
  sensibles et migrer `backend/services/storage_engine.py` dessus.

## 8. Secrets en production

Le pattern actuel (`.env` + `pydantic-settings` côté `backend/`, `.env` + `python-dotenv` côté
`src/`) n'a **pas besoin de changer** : en prod, `fly secrets set` (ou l'équivalent Railway/Vercel)
injecte les mêmes variables d'environnement, lues exactement de la même façon par
`backend/core/config.py` et `src/secrets_config.py`. Un secrets manager dédié (Doppler) reste une
option si plusieurs plateformes doivent partager les mêmes secrets sans les dupliquer à la main —
non nécessaire tant qu'un seul environnement de prod est en jeu.

## 9. Monitoring

- **`/health`** : déjà exposé par `backend/main.py` et `src/crm_api.py` — les enregistrer dans
  [UptimeRobot](https://uptimerobot.com) (gratuit) une fois les URLs de prod connues.
- **Flower** (monitoring des tâches Celery) : ne pas exposer publiquement en l'état (`docker-compose.yml`
  ne l'expose qu'en dev, sans authentification) — en prod, le lancer derrière le même mécanisme
  d'auth que Streamlit (§3), ou ne le lancer que ponctuellement en `fly ssh console` / tunnel local.
- **Sentry** : un projet par process (backend, streamlit, portail) recommandé pour ne pas mélanger
  les alertes ; DSN à générer sur [sentry.io](https://sentry.io) et à renseigner dans les variables
  d'environnement respectives (`SENTRY_DSN` ×2, `NEXT_PUBLIC_SENTRY_DSN`).

---

## Ce qui manque encore

- Aucun compte réel créé à ce jour (Fly.io, Vercel, Upstash, Sentry, UptimeRobot) — cette page
  documente la procédure, pas un déploiement effectué.
- Test de restauration Neon (§4) non exécuté.
- Object Lock S3 (§7) à vérifier sur le bucket existant, potentiellement à recréer.
- CSP du portail (`frontend-portail/next.config.js`) est resserrée mais pas strictement
  nonce-based (garde `'unsafe-inline'` pour `script-src`/`style-src`, nécessaire au bootstrap
  Next.js sans configuration supplémentaire) — durcissement possible plus tard via
  `middleware.ts` + nonces si besoin.
