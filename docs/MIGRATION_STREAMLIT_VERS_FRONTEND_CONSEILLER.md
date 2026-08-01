# Migration : de Streamlit (`src/`) vers `frontend-conseiller/` (Next.js)

## Objectif de ce document

Lister concrètement tout ce qu'il faut faire pour que `frontend-conseiller/` puisse remplacer `src/app.py` (Streamlit) comme outil de travail quotidien des conseillers, sans perte de fonctionnalité. Basé sur un état des lieux précis du code existant (`backend/routers/`, `backend/services/`, `backend/models/`) comparé à ce que fait réellement `src/app.py`.

**Constat de départ** : `backend/` n'est pas parti de zéro — `Client` et `Prospect` sont explicitement des *miroirs* des tables SQLite (`backend/models/prospect.py`, `client.py`), et une partie du workflow (dossier, honoraires, portail, veille) est déjà portée et plus avancée que Streamlit. Le travail restant est donc inégal selon les modules : certains n'ont qu'une UI à écrire, d'autres nécessitent encore de la logique métier côté backend.

## Principe de migration recommandé

**Bascule progressive, module par module, jamais un big-bang.** Le disjoncteur déjà présent dans `src/api_client.py` prouve que le projet a l'habitude de faire cohabiter plusieurs sources de vérité sans casser la prod — le même esprit doit guider la migration :

1. Un module n'est migré que lorsque le backend expose **la parité fonctionnelle complète** (pas juste le CRUD), vérifiée par des tests `backend/tests/`.
2. Le conseiller garde accès à Streamlit pour les modules non encore migrés (les deux outils cohabitent, chacun sur son URL) — pas de coupure forcée.
3. On n'arrête `src/app.py` en production que lorsque **tous** les modules ci-dessous sont cochés « migré ».
4. `frontend-portail/` (déjà livré) et `src/chatbot_api.py` (public, indépendant) ne sont pas concernés par cette migration — ils restent tels quels.

## Vue d'ensemble : ce qui manque, module par module

| Module Streamlit | Backend Postgres | Manque côté **backend** | Manque côté **frontend-conseiller** |
|---|---|---|---|
| Authentification / rôles | `routers/auth.py`, `core/security.py` | Rien — parité complète, déjà utilisé par le socle actuel | Rien — déjà fait (login, cookies, refresh) |
| Clients & contrats | `routers/clients.py` | CRUD ok. Pas d'équivalent de `note_couverture_par_zone` / `meilleur_debit_par_zone` (couverture réseau par ville) | Toute l'UI (liste, fiche, formulaire, contrats) |
| Prospects | `routers/prospects.py` | CRUD ok, `score` existe en base **mais aucun endpoint ne calcule le score** (`calculer_score_prospect` n'est pas porté) ; **pas d'endpoint de conversion prospect → client** (`finaliser_conversion_client` référencé seulement en commentaire dans `models/dossier.py`) ; pas de génération de token d'upload de documents *avant* conversion (`TokenPublic` est lié à `client_id` obligatoire, pas à un prospect) | Toute l'UI (liste, fiche, scoring affiché, bouton conversion) |
| Diagnostic / comparateur d'offres | `routers/offres.py` (`/comparer`, `/recommandations`) | À vérifier : couvre-t-il les 3 univers (télécom/énergie/abonnements) comme `src/offres_engine.py` ? Pas de génération PDF de restitution hors contexte "dossier" (`restitution_pdf_engine.py` semble lié à un `Dossier` existant) | Tout l'assistant en 4 étapes + écran de restitution |
| Dossier / souscription | `routers/dossiers.py`, `services/dossier_engine.py` | **Plus avancé que Streamlit** (machine à états stricte, timeline, notes, LRE, signature Yousign) — rien à porter, juste à consommer | Toute l'UI (création dossier, transitions, timeline, envoi lien client) |
| Facturation / honoraires | `routers/honoraires.py`, `routers/factures.py` | Parité a priori correcte (mandat + analyse facture) | Toute l'UI |
| Tableau de bord | — | **Aucun endpoint d'agrégation** (KPIs, relances du jour/à venir/en retard) — Streamlit calcule ça en lisant SQLite directement | UI + logique d'agrégation (calculable côté frontend à partir de `/clients` + `/prospects`, ou à endpoint dédié si le volume grossit) |
| Veille prix | `routers/veille.py`, `services/veille_engine.py` | Parité a priori correcte (sources, historique, alertes) | UI admin (sources, historique, alertes) |
| Alertes offres moins chères | `routers/alertes_offres.py` | Parité a priori correcte | UI de validation/rejet |
| Catalogue d'offres auto-alimenté | — | **Absent.** `catalogue_engine.py`, tables `catalogue_sources`/`offres_staging` n'existent qu'en SQLite | Rien à faire tant que le backend n'existe pas |
| Recherche plein texte (FTS) | — | **Absent.** Aucun endpoint de recherche transverse trouvé | À arbitrer : filtre client-side en attendant, ou porter le FTS |
| Agent d'audit autonome | — | **Absent** (`src/audit_agent.py`) | Hors périmètre immédiat, à traiter à part |
| Chatbot public | `src/chatbot_api.py` (service séparé) | N/A — reste indépendant, pas un module de `frontend-conseiller` | N/A |
| Admin : utilisateurs | `routers/auth.py` (partiel) | Vérifier la présence d'un CRUD utilisateurs complet (création, désactivation) | UI |
| Admin : paramètres | `routers/parametres.py` | Parité a priori correcte (réglages + logo) | UI |
| Admin : OCR facture (Vision) | `routers/factures.py` + `services/facture_analyzer.py` | Parité a priori correcte | UI |

> Les lignes « à vérifier » doivent être confirmées endpoint par endpoint avant de démarrer chaque module — ce tableau donne la direction, pas une garantie à 100 %.

## Détail par domaine

### 1. Prospects — le module le plus lacunaire côté backend

Trois briques métier à porter de `src/prospects_engine.py` vers `backend/services/` **avant** de construire l'UI, sinon le frontend n'aurait rien à appeler :

- **Scoring** : porter `calculer_score_prospect` / `expliquer_score_prospect` en service backend, exposer via un champ calculé à la lecture ou un endpoint dédié (`GET /prospects/{id}/score` ou calcul à la volée dans `ProspectOut`).
- **Conversion en client** : créer l'endpoint manquant (`POST /prospects/{id}/convertir`) qui reproduit `finaliser_conversion_client` — création du `Client`, bascule `Dossier.est_prospect` à `False` (le champ existe déjà, la logique non).
- **Documents avant conversion** : décider si on élargit `TokenPublic`/`token_engine.py` pour accepter un `prospect_id`, ou si l'on impose la conversion en client avant tout upload de document (changement de parcours assumé). C'est un choix produit à trancher avec l'équipe métier, pas juste technique.

### 2. Diagnostic / comparateur

Avant de construire l'assistant 4 étapes dans `frontend-conseiller/app/(conseiller)/diagnostic/`, vérifier que `backend/services/offres_engine.py` couvre bien télécom **+** énergie **+** abonnements (le `src/offres_engine.py` legacy le fait) — sinon porter ce qui manque. Vérifier aussi que `restitution_pdf_engine.py` peut générer un PDF de restitution **sans dossier existant** (au moment du diagnostic, aucun dossier n'a encore été créé) ; sinon, soit créer le dossier plus tôt dans le parcours, soit ajouter un mode « brouillon ».

### 3. Tableau de bord

Pas de gap métier réel — juste un choix d'implémentation : agréger côté frontend (fetch `/clients` + `/prospects`, filtrer sur `date_relance` côté client) tant que les volumes restent petits, ou ajouter un endpoint d'agrégation côté backend si la liste devient trop grosse pour être rapatriée en entier à chaque chargement du dashboard.

### 4. Admin

Chaque sous-onglet Streamlit devient probablement une sous-route (`/admin/utilisateurs`, `/admin/veille`, `/admin/parametres`…). Le catalogue auto-alimenté et l'agent d'audit n'ont pas d'équivalent backend : soit ils restent sur Streamlit plus longtemps (module « en dernier »), soit ils sont sciemment abandonnés/repensés — décision produit à prendre, pas à deviner.

## Points transverses à trancher avant d'attaquer le contenu métier

- **Requêtage de données** : `frontend-conseiller` n'a aujourd'hui aucune lib de state/fetch (pas de React Query/SWR). À choisir avant la première page de données — évite de réinventer le cache/refetch à chaque module.
- **UI kit** : seul Tailwind est posé, pas de composants (tables, formulaires, modales). Décider d'une lib (ou de composants maison) avant de dupliquer du code entre les 6 sections.
- **Formulaires** : le diagnostic et les fiches client/prospect ont des formulaires multi-étapes/multi-champs assez lourds côté Streamlit — prévoir une lib de formulaires (validation, étapes) plutôt que du `useState` manuel partout.
- **Upload de fichiers** : le portail client (`frontend-portail`) le fait déjà en direct vers `backend/services/storage_engine.py` (S3 Scaleway) — réutiliser le même pattern côté conseiller (upload de facture pour l'OCR, documents).
- **Génération/téléchargement de PDF** : `restitution_pdf_engine.py` génère côté backend ; le frontend n'a qu'à déclencher l'appel et proposer le téléchargement (pas de génération PDF côté Next.js).
- **Notifications** : les emails/SMS restent gérés par `backend/services/notification_engine.py` + Celery — aucun travail frontend au-delà de déclencher les actions (envoyer lien client, relancer).
- **Gestion du backend indisponible** : `frontend-conseiller` n'a pas aujourd'hui l'équivalent du disjoncteur `src/api_client.py`. À ce stade (backend obligatoire, pas de mode dégradé, cf. `LANCEMENT.md`), c'est un choix assumé — à revoir seulement si la disponibilité du backend devient un problème réel en prod.
- **Rôles** : le pattern garde-page + lien masqué déjà utilisé pour `/admin` (`estAdmin()` dans `AuthContext`) est le modèle à reproduire pour toute future restriction fine (ex. lecture seule pour un rôle donné), si ce besoin existe côté Streamlit.
- **Tests** : `frontend-conseiller` n'a aucune suite de tests JS (`npm run lint` seulement). Décider a minima d'ajouter des tests sur la logique de scoring/conversion si elle est portée côté backend (là, `backend/tests/` est la bonne place, pattern déjà suivi pour `test_offres_engine.py`/`test_veille_engine.py`).
- **Déploiement** : `frontend-conseiller` tourne sur le port **3001**, distinct de Streamlit (**8501**) et de `frontend-portail` — les deux outils peuvent tourner en parallèle sans conflit pendant toute la transition.

## Ordre de priorité suggéré

1. **Backend d'abord, pour les modules lacunaires** : scoring + conversion prospect (bloque tout le module Prospects), vérification de parité du comparateur (bloque Diagnostic).
2. **Clients & Prospects** — CRUD déjà prêt côté backend pour l'essentiel, gain rapide une fois les deux points ci-dessus réglés.
3. **Dossier / Facturation** — backend déjà en avance, uniquement de l'UI à écrire ; bon module pour poser le UI kit et le pattern de fetch qui serviront aux autres pages.
4. **Diagnostic** — le plus gros morceau d'UI (assistant multi-étapes), à faire une fois le pattern de formulaires choisi.
5. **Tableau de bord** — rapide une fois Clients/Prospects branchés (dépend de leurs données).
6. **Admin** — en dernier, sous-module par sous-module ; catalogue et agent d'audit traités à part (décision produit préalable).

## Definition of done — quand éteindre Streamlit

- Les 6 sections de `frontend-conseiller` couvrent au moins les mêmes actions que les 6 menus Streamlit correspondants (voir tableau §1).
- Les 3 briques manquantes du module Prospects (scoring, conversion, documents pré-conversion) sont portées et testées côté backend.
- Le catalogue et l'agent d'audit ont une décision produit actée (portés, remplacés, ou abandonnés) — pas laissés en silence.
- Les conseillers ont été formés/basculés sur `frontend-conseiller` pour chaque module migré, avec un retour arrière possible (Streamlit encore accessible) pendant une période de rodage.
