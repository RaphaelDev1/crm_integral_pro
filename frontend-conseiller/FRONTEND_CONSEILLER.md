# `frontend-conseiller/` — ce que fait cette application

## En une phrase

C'est le futur **outil interne des conseillers** (remplaçant destiné à `src/app.py` / Streamlit), en Next.js, connecté au backend FastAPI (`backend/`). À ce jour, **seul le socle technique est livré** : authentification, navigation, protection des routes. Le contenu métier de chaque page (clients, prospects, facturation, diagnostic, admin) est encore vide.

À ne pas confondre avec `frontend-portail/`, qui est le portail **client final**, public, sans compte, accessible par lien à token.

## Statut actuel : socle livré, contenu à venir

Chaque page de `app/(conseiller)/` (`dashboard`, `clients`, `prospects`, `facturation`, `diagnostic`, `admin`) est un stub de 8 lignes (32 pour `admin`, qui contient déjà la garde de rôle). Aucune n'affiche encore de données réelles. Ce qui existe déjà et fonctionne :

- connexion / déconnexion réelles contre le backend ;
- protection de toutes les routes derrière l'authentification ;
- rafraîchissement automatique de session ;
- distinction conseiller / admin ;
- layout (Header + Sidebar) commun à toutes les pages.

## Architecture technique

### Le proxy BFF — pourquoi et comment

Le navigateur **ne parle jamais directement** au backend FastAPI (`:8000`). Toutes les requêtes passent par un proxy same-origin :

```
app/api/backend/[...path]/route.ts
```

Ce proxy lit les cookies `access_token` / `refresh_token` (posés en **HttpOnly**, donc invisibles et invulnérables au JS/XSS), rajoute le header `Authorization: Bearer <token>`, et relaie la requête vers `BACKEND_URL` (variable serveur, lue au runtime — pas figée au build Docker).

Deux conséquences importantes :
- le backend n'a **jamais besoin d'autoriser `localhost:3001` en CORS** — pour lui, l'appelant est toujours le serveur Next.js ;
- un token n'est **jamais exposé côté client** — aucune faille XSS ne peut l'exfiltrer.

### Authentification

- `app/api/auth/login/route.ts`, `.../logout/route.ts`, `.../refresh/route.ts` — routes serveur qui posent/suppriment les cookies.
- `lib/server/backend.ts` / `lib/server/refreshAccessToken.ts` — appels serveur vers le backend, gestion du refresh silencieux (access token 1h, refresh token 7 jours).
- `contexts/AuthContext.tsx` — expose `estAdmin()` et l'état de session côté client.
- `middleware.ts` — bloque toute page hors `/login` et `/api/*` si le cookie `access_token` est absent. **Ce n'est qu'un filtre d'ergonomie** (pas de vérification de signature côté edge) : c'est le backend qui reste seule autorité sur la validité réelle du token, chaque endpoint revalidant le rôle (cf. commentaire dans `admin/page.tsx`).
- Premier compte admin créé par `python -m backend.scripts.seed_admin`, avec `doit_changer_mdp=True` forçant un changement de mot de passe à la première connexion.

### Navigation et layout

- `app/(conseiller)/layout.tsx` — layout commun (Header + Sidebar) pour les 6 sections.
- `components/layout/Header.tsx`, `components/layout/Sidebar.tsx` — la Sidebar masque déjà le lien "Admin" pour les non-admins (double protection avec la garde dans `admin/page.tsx`).
- `app/login/page.tsx` — page de connexion, seule route publique avec `/api/*`.

### Dépendances (`package.json`)

Stack volontairement minimale : `next@14.2.35`, `react@18.3.1`, `@sentry/nextjs` (monitoring d'erreurs), `lucide-react` (icônes), Tailwind CSS + TypeScript en dev. **Aucune librairie de state management** (pas de Redux/Zustand/React Query…) et **aucun kit de composants UI** au-delà de Tailwind — tout est à choisir/poser lors de la construction du contenu métier.

### Lancement

Port dédié **3001** (`next dev -p 3001`), backend FastAPI requis sur `:8000` (aucun mode mock). Procédure complète : `frontend-conseiller/LANCEMENT.md`.

## Les 6 sections prévues (aujourd'hui vides)

| Route | Rôle prévu (à construire) | Équivalent Streamlit |
|---|---|---|
| `/dashboard` | KPIs, relances du jour/à venir/en retard | menu `📊 Tableau de bord` |
| `/clients` | Liste + fiche client, contrats | menu `👥 Clients & contrats` |
| `/prospects` | Liste + fiche prospect, scoring, conversion en client | menu `📇 Prospects` |
| `/facturation` | Devis d'honoraires, mandat, suivi paiement | menu `🧾 Facturation` |
| `/diagnostic` | Assistant de diagnostic (univers → situation → recommandations) | menu `🧭 Nouveau diagnostic` |
| `/admin` (accès restreint) | Utilisateurs, catalogue, veille prix, paramètres | menu `🛠️ Admin` |

Le détail de ce qu'il faut construire pour remplir chacune de ces pages, endpoint par endpoint, est dans `docs/MIGRATION_STREAMLIT_VERS_FRONTEND_CONSEILLER.md`.

## À retenir avant d'y travailler

1. Toujours passer par le proxy BFF (`app/api/backend/...`) depuis le client — jamais d'appel direct à `BACKEND_URL` dans un composant client.
2. Ne pas dupliquer la vérification de rôle uniquement côté middleware/UI : le backend revalide déjà, mais l'UI doit rester cohérente (masquer + garder + rediriger, comme fait pour `/admin`).
3. Aucune suite de tests JS n'existe encore ici (`npm run lint` seulement) — la couverture métier reste côté `backend/tests` et `src/tests`.
