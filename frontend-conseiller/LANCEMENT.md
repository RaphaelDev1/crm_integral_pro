# Lancer le frontend-conseiller — guide étape par étape

> Périmètre : uniquement `frontend-conseiller/` (outil interne Next.js pour les conseillers,
> distinct de `frontend-portail/` qui est le portail client). Ce frontend ne parle jamais
> directement au backend depuis le navigateur : toutes les requêtes passent par un proxy BFF
> same-origin (`app/api/backend/[...path]/route.ts`), qui lit les cookies HttpOnly
> `access_token`/`refresh_token` et les transmet au backend FastAPI avec le header `Authorization`.
> C'est pourquoi le backend n'a pas besoin d'autoriser `http://localhost:3001` en CORS.

---

## 0. Pré-requis

- Node.js 20 (voir `Dockerfile`, image `node:20-slim`).
- Le **backend FastAPI doit tourner** (aucune fonctionnalité ne marche sans lui — pas de mode
  mock). Voir étape 1.
- Un compte Postgres accessible (Neon en dev, ou un Postgres local via `docker compose --profile local-db up`).

## 1. Démarrer le backend (obligatoire, à faire avant le frontend)

Dans un terminal séparé, à la racine du dépôt :

```powershell
# 1a. Config (une seule fois)
Copy-Item backend/.env.example backend/.env
# Remplir au minimum dans backend/.env : DATABASE_URL, CRM_API_SECRET
# (générer avec : python -c "import secrets; print(secrets.token_urlsafe(48))")

# 1b. Dépendances (une seule fois)
pip install -r backend/requirements-dev.txt

# 1c. Migrations Alembic (obligatoire avant tout)
python -m alembic upgrade head
python -m alembic current   # doit afficher "0020 (head)"

# 1d. Créer le tout premier compte admin (table utilisateurs vide uniquement)
python -m backend.scripts.seed_admin
# Affiche l'identifiant "admin" et un mot de passe généré une seule fois — le noter.
# Ne fait rien si un compte existe déjà (idempotent).

# 1e. Lancer le backend
uvicorn backend.main:app --reload --port 8000
```

Vérification : `http://localhost:8000/health` → `200 OK`, `http://localhost:8000/docs` → Swagger.

> Le worker Celery (`backend/workers/celery_app.py`) et Redis ne sont nécessaires que pour la
> validation KYC async et l'envoi Yousign — pas requis pour se connecter et naviguer dans
> frontend-conseiller/.

## 2. Configurer frontend-conseiller

```powershell
cd frontend-conseiller
```

Le fichier `.env.local` existe déjà (gitignored) et pointe sur le backend local :

```
BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_SENTRY_DSN=
```

S'il est absent :

```powershell
Copy-Item .env.example .env.local
```

`NEXT_PUBLIC_SENTRY_DSN` peut rester vide en dev — Sentry s'initialise sans rien envoyer.

## 3. Installer les dépendances

```powershell
npm install
```

## 4. Lancer en dev

```powershell
npm run dev
```

Démarre sur **`http://localhost:3001`** (voir `"dev": "next dev -p 3001"` dans `package.json`).

## 5. Se connecter

1. Ouvrir `http://localhost:3001` → redirection automatique vers `/login` (middleware,
   `frontend-conseiller/middleware.ts`, car aucun cookie `access_token`).
2. Se connecter avec l'identifiant/mot de passe `admin` généré à l'étape 1d.
3. `doit_changer_mdp=True` sur ce compte : un changement de mot de passe sera exigé à la première
   connexion.
4. Redirection vers `/dashboard`.

## 6. Vérifications rapides

- `http://localhost:3001/login` → formulaire de connexion s'affiche.
- Connexion réussie → cookies `access_token`/`refresh_token` posés (HttpOnly, visibles dans
  DevTools > Application > Cookies, pas en JS).
- Toutes les routes ci-dessous accessibles une fois connecté (aucune ne doit renvoyer une page
  blanche ni une erreur non gérée) :

  | Route | Contenu |
  |---|---|
  | `/dashboard` | KPIs + relances |
  | `/clients`, `/clients/[id]` | Liste clients + fiche détail |
  | `/prospects`, `/prospects/[id]` | Liste prospects + fiche détail (scoring, conversion) |
  | `/dossiers`, `/dossiers/[id]` | Liste dossiers + fiche timeline |
  | `/facturation` | Mandats honoraires, analyse factures |
  | `/diagnostic` | Wizard 4 étapes (identité, situation, univers, recommandations) |
  | `/admin` | Landing admin |
  | `/admin/utilisateurs` | Gestion des comptes conseillers |
  | `/admin/parametres` | Paramètres app (logo, etc.) |
  | `/admin/veille` | Sources de veille prix |
  | `/admin/catalogue` | Sources à ingérer + offres détectées (staging) — voir §7.6 |
  | `/admin/ocr-facture` | OCR/analyse de factures |

- Couper le backend (`Ctrl+C` sur uvicorn) puis recharger une page protégée → erreur propre côté
  proxy (`app/api/backend/[...path]/route.ts`), pas de crash silencieux.
- Laisser expirer l'`access_token` (1h) : le refresh via `refresh_token` (7 jours) doit se faire de
  façon transparente (`lib/server/refreshAccessToken.ts`) ; au-delà de 7 jours, retour à `/login`.

## 7. Tester chaque module fonctionnel pas à pas

Ordre suggéré (les modules 7.1 → 7.4 dépendent les uns des autres : créer un prospect avant de le
convertir, un client avant un dossier).

**7.1 — Prospects**
1. `/prospects` → « Nouveau prospect » → remplir le formulaire → vérifier l'apparition dans la
   liste (React Query invalide bien le cache après la mutation).
2. Ouvrir la fiche `/prospects/[id]` → déclencher le scoring → vérifier qu'un score s'affiche.
3. Depuis la fiche, lancer la conversion prospect → client → vérifier la redirection/lien vers la
   fiche client créée et que le prospect passe au statut « converti ».

**7.2 — Clients**
1. `/clients` → liste paginée/filtrable → ouvrir une fiche `/clients/[id]`.
2. Vérifier l'onglet contrats de la fiche client.

**7.3 — Dossiers**
1. `/dossiers` → liste → ouvrir une fiche `/dossiers/[id]` → vérifier la timeline des étapes.
2. Vérifier la génération PDF de restitution si le dossier est au bon statut.

**7.4 — Facturation**
1. `/facturation` → mandat d'honoraires : créer/vérifier un mandat.
2. Uploader une facture → vérifier l'analyse (extraction/alertes) et son affichage.

**7.5 — Diagnostic**
1. `/diagnostic` → parcourir les 4 étapes du wizard (identité, situation, univers,
   recommandations) jusqu'au bout sans erreur de validation Zod bloquante.
2. Vérifier que l'étape recommandations appelle bien l'agent d'audit backend
   (`backend/services/audit_agent.py`) et affiche un résultat chiffré et traçable.

**7.6 — Admin : catalogue auto-alimenté**
1. `/admin/catalogue` → ajouter une source (page tarifs officielle réelle).
2. Déclencher l'ingestion → vérifier que le résultat tombe dans les offres détectées
   (`offres_staging`), jamais directement dans le catalogue actif.
3. Valider/rejeter une offre détectée → vérifier son passage (ou non) dans le catalogue actif.

**7.7 — Admin : veille prix, paramètres, utilisateurs, OCR facture**
1. `/admin/veille` → créer une source de veille, vérifier l'historique des relevés/alertes.
2. `/admin/parametres` → modifier un paramètre (ex. logo) → vérifier la persistance.
3. `/admin/utilisateurs` → créer un second compte conseiller, se déconnecter, se reconnecter avec.
4. `/admin/ocr-facture` → uploader une facture test → vérifier l'extraction.

## 8. Lancer les tests / lint

```powershell
npm run lint
npm test           # vitest — tests unitaires/composants
npm run test:e2e   # playwright — parcours complets (login, clients, diagnostic), démarre le
                    # serveur dev automatiquement (voir playwright.config.ts) ; nécessite le
                    # backend déjà lancé (étape 1) car aucun mock n'est utilisé
```

(Couverture JS encore partielle — la couverture métier la plus large reste côté `backend/tests` et
`src/tests`.)

## 9. Régénérer les types API

`lib/api-types.ts` est généré depuis `http://localhost:8000/openapi.json` (backend démarré, voir
étape 1) :

```powershell
npm run types:api
```

**À relancer après chaque changement de schéma Pydantic côté backend** (nouveau champ, nouvelle
route…) pour que les types TypeScript restent synchronisés.

## 10. Build production / Docker

```powershell
npm run build
npm run start   # sert sur :3001
```

Ou via Docker (contexte = `frontend-conseiller/`) :

```powershell
docker build -t ia-conseil-frontend-conseiller frontend-conseiller
docker run -p 3001:3001 -e BACKEND_URL=http://backend:8000 ia-conseil-frontend-conseiller
```

`BACKEND_URL` n'est **pas** figé au build (lu uniquement côté serveur au runtime) : passer la
vraie valeur via `-e BACKEND_URL=...` selon l'environnement cible.

## 11. Problèmes fréquents

| Symptôme | Cause | Solution |
|---|---|---|
| Boucle infinie vers `/login` | Backend arrêté ou `DATABASE_URL` invalide | Vérifier `http://localhost:8000/health` |
| Connexion échoue avec identifiant/mot de passe corrects | Pas de compte encore créé | Relancer `python -m backend.scripts.seed_admin` (table `utilisateurs` vide requise) |
| Le JS ne s'exécute pas du tout en dev, aucune requête au clic sur "Se connecter" | CSP trop stricte sans `unsafe-eval` | Déjà géré : `next.config.js` ajoute `'unsafe-eval'` uniquement quand `NODE_ENV !== "production"` (Fast Refresh) |
| 401 en boucle après connexion | Horloge système désynchronisée ou `CRM_API_SECRET` différent entre lancements backend | Vérifier que `backend/.env` n'a pas changé de `CRM_API_SECRET` entre deux sessions |
