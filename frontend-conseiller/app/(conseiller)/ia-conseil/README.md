# IA Conseil — Trame Live (Phase 1)

Sous-système neuf, isolé du CRM existant (`/clients`, `/diagnostic`, `/dossiers`)
— voir `backend/models/ia_conseil.py` et `PLAN_IMPLEMENTATION_4_PHASES.md`.
API préfixée `/api/v1/*`, catalogue/clients/souscriptions séparés du CRM.

## Routes

| Route | Rôle |
|---|---|
| `/ia-conseil/clients` | Liste + création des clients IA Conseil |
| `/ia-conseil/clients/[id]` | Fiche client, choix catégorie/canal, démarrage de trame |
| `/ia-conseil/clients/[id]/trame/[sessionId]` | **Vue pivot** — trame adaptative en direct (3 colonnes) |
| `/ia-conseil/admin/catalogue` | CRUD admin du catalogue (offres mobile/box/énergie) |
| `/ia-conseil-partage/[sessionId]?token=...` | Vue lecture-seule envoyée au client (hors auth conseiller, hors `(conseiller)`) |

## Vue pivot — 3 colonnes (`TrameLayout`)

- **Gauche** (`ProgressTree`) : historique de la session en cours (l'API ne renvoie qu'une
  question à la fois — principe "escargot" — donc l'historique n'est reconstruit
  qu'au fil de la navigation, pas depuis `session.reponses` après un rechargement).
  Cliquer une réponse déjà donnée permet de la corriger ("retour arrière libre").
- **Centre** (`QuestionCard` + `AnswerInput`) : la question courante, choisie par
  `rules_engine.question_selector` côté backend.
- **Droite** (`LiveRecommandations` + `EconomieTicker`) : classement d'offres et
  économie estimée, recalculés après chaque réponse.

Le bouton **Mode présentation** grossit la question et masque les données
backoffice dans les colonnes (jamais les recommandations elles-mêmes — c'est
ce qu'on montre au client). Le bouton **Partager avec le client** génère un
lien lecture-seule (`/ia-conseil-partage/...`) valable 30 jours.

## Temps réel

Le navigateur ne parle jamais directement au backend (voir `.env.example` /
`lib/api.ts`). Le flux temps réel passe par un relais SSE côté serveur
(`app/api/ia-conseil-live/[sessionId]/route.ts`) qui maintient la connexion
WebSocket vers le backend (JWT lu depuis le cookie httpOnly) et retransmet
chaque message via Server-Sent Events — consommé côté client par
`lib/hooks/useSessionTrameLive.ts`.

## Ce qui reste hors scope de cette itération

- Sources catalogue live (APIs partenaires réelles, scrapers) : seule
  l'architecture est posée (`backend/services/ia_conseil_catalogue_sync.py`,
  interface d'adapter + tâche Celery planifiée) — le CRUD admin reste le
  canal réel de mise à jour du catalogue.
- Options `select` avec `options_ref` (référentiels comme "opérateurs
  mobiles") : pas de référentiel exposé par l'API, `AnswerInput` retombe en
  saisie libre pour ces questions.
