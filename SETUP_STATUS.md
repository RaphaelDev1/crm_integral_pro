# Setup IA Conseil — Statut

## Complété ✅

- [x] Modèles `Dossier`, `TokenPublic`, `Commission`, `Abonnement` (`backend/models/`)
- [x] Migration Alembic `0003_dossiers_tokens_commissions.py` créée (`alembic history` la voit en tête : `0002 -> 0003 (head)`)
- [x] Schémas Pydantic `backend/schemas/dossier.py` et `backend/schemas/portail_public.py`
- [x] Services `token_engine`, `dossier_engine`, `storage_engine` (`backend/services/`)
- [x] Routers `dossiers` (protégé JWT) et `portail_public` (accès par lien unique, sans login)
- [x] `backend/core/config.py` étendu (portail client, S3, Stripe, SMS, Resend)
- [x] `backend/main.py` : CORS activé pour le portail Next.js, nouveaux routers branchés
- [x] `backend/requirements.txt` : ajout `boto3`, `stripe`, `resend`
- [x] `backend/.env.example` complété (S3, Stripe, SMS, Resend, portail client)
- [x] Dépendances Python installées (`boto3`, `stripe`, `resend`, `python-multipart`)
- [x] Portail Next.js `frontend-portail/` créé, installé (`npm install`) et build vérifié (`npm run build` ✅)
- [x] `.gitignore` mis à jour (`frontend-portail/node_modules`, `.next`, `.env.local`)
- [x] Suite de tests backend existante : **14/14 passés** (rien de cassé côté Streamlit/API existante)
- [x] Serveur FastAPI démarré et vérifié : `/health` OK, tous les endpoints attendus présents dans `/openapi.json`
- [x] Portail Next.js démarré et vérifié : `http://localhost:3000` affiche bien la landing page

## ✅ Point bloquant résolu — Postgres (Neon)

`DATABASE_URL` pointe maintenant vers un projet Neon (pooler, région eu-west-2). Migration appliquée avec
succès : `alembic current` renvoie `0003 (head)`. Toutes les tables (existantes + `dossiers`,
`tokens_publics`, `commissions`, `abonnements`) sont créées.

Deux ajustements ont été nécessaires pour que le driver `asyncpg` fonctionne avec l'URL Neon fournie :
- `channel_binding=require` retiré de l'URL — paramètre spécifique à `libpq`/`psycopg`, non supporté par `asyncpg`.
- `sslmode=require` remplacé par `ssl=require` — `asyncpg` n'accepte `ssl` que sous ce nom quand il est
  passé en paramètre de requête (et non intégré dans un DSN complet).
- `backend/core/database.py` : ajout de `connect_args={"statement_cache_size": 0}` sur l'engine —
  requis car Neon expose un endpoint **pooler** (PgBouncer, transaction pooling) ; sans ce réglage,
  le cache de requêtes préparées d'`asyncpg` peut provoquer des erreurs intermittentes
  `prepared statement does not exist` quand PgBouncer bascule la session sur une autre connexion
  physique entre deux requêtes.

Vérifié : `/health` OK, `/auth/login` exécute bien une requête SQL réelle contre la base (401 "identifiant
incorrect", pas une erreur de connexion), 14/14 tests backend toujours au vert.

## ℹ️ Écart mineur par rapport à la demande initiale

Le portail Next.js a été épinglé sur **`next@14.2.35`** au lieu de `14.2.5` : la version 14.2.5 contient
une faille de sécurité critique corrigée par les patchs 14.2.x ultérieurs (cache poisoning, DoS...).
`npm audit` signale qu'il reste des vulnérabilités seulement corrigibles en passant à Next 16 (changement
majeur, non rétrocompatible) — décision à prendre plus tard si besoin, pas bloquant pour le développement.

## À faire manuellement par toi (Raphael) 🤝

1. **Compte Anthropic** (obligatoire pour KYC LLM)
   - Créer un compte sur console.anthropic.com
   - Générer une clé API
   - La mettre dans `backend/.env` : `ANTHROPIC_API_KEY=sk-ant-...`

2. **Bucket S3 Scaleway** (obligatoire pour upload documents)
   - Créer un compte sur console.scaleway.com
   - Créer un bucket Object Storage privé "ia-conseil-kyc" en région fr-par
   - Créer une clé API dédiée avec permissions Object Storage
   - Remplir dans `backend/.env` : `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`

3. **Compte Yousign** (pour la signature électronique — Sprint 3)
   - Inscription sur developers.yousign.com (sandbox gratuit)
   - Récupérer clé API et secret webhook
   - Remplir dans `.env` : `YOUSIGN_API_KEY`, `YOUSIGN_WEBHOOK_SECRET`

4. **Avocat** (BLOQUANT commercial)
   - Contacter un avocat spécialisé (droit du numérique + consommation)
   - Faire valider : mandat de représentation, CGU, RGPD, mention double rémunération
   - Budget ~1500€
   - Inclut désormais la relecture des textes de courrier de démarche (résiliation, portabilité,
     changement de fournisseur) générés par `backend/services/document_engine.py` — boilerplate non
     encore validé juridiquement.

5. **Compte AR24** (pour l'envoi LRE des démarches — Chantier 3, génération automatique des démarches)
   - Inscription sur ar24.fr, récupérer une clé API (sandbox si disponible)
   - Vérifier le schéma d'authentification exact (bearer token vs login/mot de passe) contre la doc AR24
     réelle — `backend/services/lre_engine.py` suppose un bearer token, à confirmer avant mise en prod
   - Remplir dans `backend/.env` : `AR24_API_KEY` (+ `AR24_LOGIN`/`AR24_PASSWORD` si nécessaire)
   - Sans cette clé, la génération de document fonctionne mais l'envoi LRE échoue proprement
     (`Demarche.statut="echouee"`, jamais de silence ni de crash)

## Test end-to-end à faire

1. Lancer backend : `uvicorn backend.main:app --reload`
2. Lancer frontend : `cd frontend-portail && npm run dev`
3. Aller sur http://localhost:8000/docs
4. POST /auth/login → récupérer access_token
5. Autoriser dans Swagger
6. POST /clients (créer un client test)
7. POST /dossiers (créer un dossier avec client_id précédent)
8. POST /dossiers/{id}/token-client → récupérer l'URL
9. Ouvrir l'URL dans un navigateur incognito → doit afficher le portail client
