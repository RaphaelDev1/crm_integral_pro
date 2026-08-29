# PLAN D'IMPLÉMENTATION — TRAME CONSEIL INTELLIGENTE
## De A à Z, en 4 phases, prêt pour Claude Code

> **Périmètre MVP** : Mobile + Box Internet + Énergie (élec/gaz)
> **Stack validée** : Next.js 14 (App Router) + FastAPI + **PostgreSQL 15** + Redis + SQLAlchemy/Alembic + Celery
> **Modèle éco** : Commission % à la souscription — **garde-fou anti-biais commercial obligatoire (§2.6)**
> **Multi-canal** : Visio (partage écran), téléphone, physique — même interface web responsive
> **Statut légal MVP** : Apport d'affaires simple (mobile/box/énergie) — pas d'ORIAS requis à ce stade

---

## 🐌 PRINCIPE #1 (NON NÉGOCIABLE) — L'ESCARGOT ADAPTATIF

**Le conseiller ne pose JAMAIS toutes les questions possibles.** La trame :

1. **Démarre par 3-5 questions socles** (composition foyer, adresse, objectif principal, catégorie ciblée).
2. **Chaque réponse ferme des branches entières** de questions devenues inutiles.
3. **La trame s'arrête dès que le moteur a assez d'infos pour produire un audit complet** — pas une question de plus.
4. **Objectif quantifié** : rendez-vous mobile bouclé en < 5 min, box < 5 min, énergie < 7 min. Un audit 3 catégories doit tenir en **15-20 min max**.

### Concrètement, comment le moteur décide quelle est la prochaine question

Pour chaque question candidate, on calcule un **score d'information** :

```
score_info(question) =
    IF (question déjà répondue OU incompatible avec réponses actuelles) → 0
    SINON :
      nombre d'offres du catalogue que cette question permettrait d'éliminer
    + nombre de règles de recommandation qui l'utilisent
    + poids éthique (une question "anti-survente" a un boost)
    - coût cognitif client (1 = simple, 3 = demande de sortir facture)
```

À chaque étape, le moteur affiche la question de score max. **Quand toutes les questions restantes ont un score < seuil, la trame est terminée.** Le conseiller peut à tout moment "creuser" volontairement (bouton "poser plus de questions") si le client veut affiner.

### Impact sur l'architecture

- Le moteur `rules_engine/` doit **calculer dynamiquement** l'ordre des questions, pas suivre un ordre figé.
- Chaque question du template a des **métadonnées** : `elimine_offres_si`, `utilise_par_regles`, `cout_cognitif`, `poids_ethique`.
- Le front reçoit UNE question à la fois via WebSocket, pas la liste complète à l'avance.
- L'utilisateur voit un **compteur "questions restantes estimées : ~4"** qui se met à jour dynamiquement pour rassurer.

Ce principe est le vrai différenciateur produit : on ne fait pas un formulaire, on fait un audit-éclair intelligent.

---

## 🎯 VISION DU RENDU FINAL

Un conseiller ouvre la fiche client dans son navigateur. Il partage son écran (visio) ou tourne l'écran (physique). Une seule interface :

- **Colonne gauche** : arbre de progression visuel (étapes cochées / en cours / à venir), s'adapte en temps réel.
- **Centre** : la question actuelle, en grand, épurée, agréable à voir même côté client.
- **Colonne droite** : score de recommandation vivant, alertes en temps réel ("attention : conso 8 Go mais forfait 200 Go proposé"), économie annuelle estimée qui se met à jour.
- **Fin de trame** : synthèse PDF générée en 1 clic, comparatif des offres, boutons de souscription pré-remplis, calendrier d'actions.

Le conseiller ne "remplit un formulaire" : il pilote une conversation guidée par la machine, qui filtre les questions inutiles et déclenche automatiquement les bonnes recommandations.

---

## 📐 ARCHITECTURE GLOBALE (à mettre en place dès Phase 0)

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND (Next.js)                     │
│  ┌───────────┐ ┌────────────┐ ┌──────────────────────────┐  │
│  │ Dashboard │ │ Trame live │ │ Recommandations + PDF    │  │
│  └───────────┘ └────────────┘ └──────────────────────────┘  │
│         │            │                    │                 │
│         │   WebSocket (temps réel)        │                 │
│         └────────────┼────────────────────┘                 │
└──────────────────────┼──────────────────────────────────────┘
                       │ REST + WS
┌──────────────────────┼──────────────────────────────────────┐
│                    BACKEND (FastAPI)                        │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  API Layer (routers) : /trames /clients /offres ...    │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  MOTEUR DE RÈGLES (rules_engine)                       │ │
│  │  - Trame dynamique (branching YAML/JSON)               │ │
│  │  - Anti-survente / anti-sous-couverture                │ │
│  │  - Scoring offres                                      │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  CATALOGUE OFFRES (offres_engine)                      │ │
│  │  - APIs partenaires (affiliés)                         │ │
│  │  - Scrapers programmés                                 │ │
│  │  - Saisie manuelle admin                               │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  AGENTS IA (agents/) — Phase 4                         │ │
│  │  - OCR facture → extraction structurée                 │ │
│  │  - Copilote conseiller (suggestion question suivante)  │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────────┐
        │              │                  │
    ┌───▼────┐   ┌─────▼─────┐    ┌──────▼─────┐
    │PostgreSQL│   │  Redis    │    │ S3/MinIO   │
    │ (data)   │   │(cache/WS) │    │ (factures) │
    └──────────┘   └───────────┘    └────────────┘
```

---

# 🟩 PHASE 0 — FONDATIONS TECHNIQUES (1-2 semaines)

**Objectif** : Poser le socle sans lequel rien ne tient. Ne pas coder d'UI pendant cette phase, uniquement la base de données, le moteur de règles et les APIs contract-first.

## 0.1 Schéma de base de données (PostgreSQL)

```sql
-- ============ CATALOGUE ============
CREATE TABLE categorie (
    id UUID PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,           -- 'mobile', 'box', 'energie_elec', 'energie_gaz'
    nom TEXT NOT NULL,
    ordre INT,
    actif BOOLEAN DEFAULT true
);

CREATE TABLE fournisseur (
    id UUID PRIMARY KEY,
    nom TEXT NOT NULL,                   -- 'Orange', 'Free', 'EDF', 'TotalEnergies'
    categorie_slug TEXT REFERENCES categorie(slug),
    note_fiabilite NUMERIC(3,2),         -- 0.00-1.00
    logo_url TEXT,
    site_url TEXT,
    affilie BOOLEAN DEFAULT false,       -- si on touche une commission
    taux_commission NUMERIC(5,2)         -- % pour nous
);

CREATE TABLE offre (
    id UUID PRIMARY KEY,
    fournisseur_id UUID REFERENCES fournisseur(id),
    categorie_slug TEXT REFERENCES categorie(slug),
    nom TEXT NOT NULL,                   -- 'Forfait 100Go 5G'
    prix_mensuel NUMERIC(10,2),
    prix_apres_promo NUMERIC(10,2),
    duree_promo_mois INT,
    engagement_mois INT DEFAULT 0,
    frais_mise_en_service NUMERIC(10,2) DEFAULT 0,
    caracteristiques JSONB NOT NULL,     -- {data_go: 100, appels_illim: true, 5g: true, roaming_ue: true, ...}
    conditions JSONB,                    -- éligibilité, restrictions
    source TEXT,                         -- 'api_partenaire' | 'scraper' | 'manuel'
    source_ref TEXT,                     -- ID côté source
    valide BOOLEAN DEFAULT true,
    date_maj TIMESTAMPTZ DEFAULT now(),
    UNIQUE(fournisseur_id, nom)
);

CREATE INDEX idx_offre_categorie ON offre(categorie_slug) WHERE valide = true;
CREATE INDEX idx_offre_caract ON offre USING gin(caracteristiques);

-- ============ TRAME ============
CREATE TABLE trame_template (
    id UUID PRIMARY KEY,
    categorie_slug TEXT REFERENCES categorie(slug),
    version INT NOT NULL,
    definition JSONB NOT NULL,           -- arbre décisionnel complet (voir §0.2)
    actif BOOLEAN DEFAULT true,
    UNIQUE(categorie_slug, version)
);

CREATE TABLE regle_recommandation (
    id UUID PRIMARY KEY,
    categorie_slug TEXT REFERENCES categorie(slug),
    nom TEXT NOT NULL,
    type TEXT CHECK (type IN ('filtre','scoring','alerte')),
    priorite INT DEFAULT 0,
    condition JSONB NOT NULL,            -- expression (voir §0.3)
    action JSONB NOT NULL,               -- {kind: 'boost'|'exclude'|'warn', payload: ...}
    actif BOOLEAN DEFAULT true
);

-- ============ CLIENTS & SESSIONS ============
CREATE TABLE client (
    id UUID PRIMARY KEY,
    conseiller_id UUID REFERENCES utilisateur(id),
    prenom TEXT, nom TEXT, email TEXT, telephone TEXT,
    adresse JSONB,                       -- {rue, cp, ville, coords{lat,lng}}
    foyer JSONB,                         -- {adultes, enfants:[{age}], statut_logement}
    profil JSONB,                        -- {objectif, sensibilite_eco, niveau_digital}
    cree_le TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE session_trame (
    id UUID PRIMARY KEY,
    client_id UUID REFERENCES client(id),
    conseiller_id UUID REFERENCES utilisateur(id),
    categorie_slug TEXT REFERENCES categorie(slug),
    trame_template_id UUID REFERENCES trame_template(id),
    reponses JSONB DEFAULT '{}'::jsonb,  -- map question_id -> réponse
    etat TEXT DEFAULT 'en_cours',        -- en_cours | terminee | abandonnee
    canal TEXT,                          -- 'visio' | 'telephone' | 'physique'
    demarree_le TIMESTAMPTZ DEFAULT now(),
    terminee_le TIMESTAMPTZ
);

CREATE TABLE recommandation (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES session_trame(id),
    offre_id UUID REFERENCES offre(id),
    score NUMERIC(5,2),
    rang INT,
    justifications JSONB,                -- ["+ moins cher de 12€/mois", "- engagement 24 mois"]
    alertes JSONB,                       -- ["ANTI_SURVENTE: 200Go pour 8Go conso"]
    economie_mensuelle NUMERIC(10,2),
    economie_annuelle NUMERIC(10,2)
);

CREATE TABLE souscription (
    id UUID PRIMARY KEY,
    client_id UUID REFERENCES client(id),
    offre_id UUID REFERENCES offre(id),
    session_id UUID REFERENCES session_trame(id),
    conseiller_id UUID REFERENCES utilisateur(id),
    date_souscription DATE,
    date_activation DATE,
    prix_mensuel_negocie NUMERIC(10,2),
    commission_prevue NUMERIC(10,2),
    commission_encaissee NUMERIC(10,2),
    statut TEXT DEFAULT 'en_attente',    -- en_attente | active | resiliee | annulee
    fin_engagement DATE
);

CREATE INDEX idx_souscription_conseiller ON souscription(conseiller_id, date_souscription);
CREATE INDEX idx_souscription_fin_engagement ON souscription(fin_engagement) WHERE statut = 'active';
```

### 0.1.bis Ajout schema pour le principe "escargot" (question minimale)

Ajouter dans chaque question du template les métadonnées :

```json
{
  "id": "conso_data_go",
  "label": "Consommation data mensuelle ?",
  "type": "number", "unit": "Go",
  "cout_cognitif": 3,               // 1=évident, 3=demande facture
  "poids_ethique": 10,              // question anti-survente = boost fort
  "elimine_offres_si": {            // pré-calculé : offres exclues selon réponse
    "reponse_lt_5":  "offres.data_go > 40",
    "reponse_lt_30": "offres.data_go > 100"
  },
  "utilise_par_regles": ["anti_survente_data_mobile", "boost_petit_rouleur"]
}
```

Le moteur utilise ces métadonnées pour scorer chaque question restante et présenter uniquement celle avec le score le plus élevé.

## 0.2 Format de la trame adaptative (JSONB `trame_template.definition`)

```json
{
  "id": "trame_mobile_v1",
  "categorie": "mobile",
  "sections": [
    {
      "id": "decouverte",
      "titre": "Découverte",
      "questions": [
        {
          "id": "nb_lignes",
          "label": "Combien de lignes mobiles dans votre foyer ?",
          "type": "number",
          "min": 1, "max": 20,
          "required": true
        },
        {
          "id": "operateur_actuel",
          "label": "Quel est votre opérateur actuel ?",
          "type": "select",
          "options_ref": "operateurs_mobiles"
        },
        {
          "id": "conso_data_go",
          "label": "Consommation data mensuelle (regarder facture 3 derniers mois)",
          "type": "number",
          "unit": "Go",
          "help": "Astuce : la moyenne est indiquée en bas de la facture",
          "required": true
        }
      ]
    },
    {
      "id": "usages",
      "titre": "Vos usages",
      "questions": [
        {
          "id": "roaming_ue",
          "label": "Voyagez-vous en Europe ?",
          "type": "select",
          "options": ["Jamais", "Occasionnellement", "Souvent"]
        },
        {
          "id": "roaming_hors_ue",
          "label": "Voyagez-vous hors UE ?",
          "type": "select",
          "options": ["Jamais", "Occasionnellement", "Souvent"],
          "show_if": {"roaming_ue": {"$ne": "Jamais"}}
        },
        {
          "id": "qualite_reseau",
          "label": "Qualité réseau perçue à votre domicile ?",
          "type": "select",
          "options": ["Bonne", "Moyenne", "Mauvaise"]
        }
      ]
    }
  ],
  "branches": [
    {
      "when": {"nb_lignes": {"$gte": 2}},
      "insert_after": "nb_lignes",
      "questions": [
        {"id": "meme_operateur_famille", "label": "Toutes les lignes chez le même opérateur ?", "type": "boolean"}
      ]
    },
    {
      "when": {"conso_data_go": {"$lt": 5}},
      "skip": ["5g_importante", "partage_connexion"],
      "flags": ["anti_survente_mobile"]
    }
  ]
}
```

**Opérateurs supportés du DSL de condition** : `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$and`, `$or`, `$not`, `$exists`.

## 0.3 Format des règles de recommandation (`regle_recommandation`)

```json
{
  "nom": "anti_survente_data_mobile",
  "type": "alerte",
  "condition": {
    "$and": [
      {"reponses.conso_data_go": {"$lt": 10}},
      {"offre.caracteristiques.data_go": {"$gt": 50}}
    ]
  },
  "action": {
    "kind": "warn",
    "severite": "critique",
    "message": "⚠️ Forfait {{offre.caracteristiques.data_go}} Go proposé alors que le client consomme {{reponses.conso_data_go}} Go/mois. Rester sur un forfait ≤ 40 Go."
  }
}
```

```json
{
  "nom": "boost_petit_rouleur_mobile",
  "type": "scoring",
  "condition": {"reponses.conso_data_go": {"$lt": 5}},
  "action": {
    "kind": "score_adjust",
    "target": "offre.caracteristiques.data_go",
    "formula": "IF(offre.data_go <= 40, +30, IF(offre.data_go <= 100, 0, -50))"
  }
}
```

## 0.4 Modules Python à créer côté backend

```
rules_engine/
├── __init__.py
├── condition_evaluator.py       # évalue le DSL {$gt, $and, ...}
├── trame_runtime.py             # gestion état session, réponses, branches
├── question_selector.py         # ★ CŒUR ESCARGOT : choisit la prochaine question
├── information_scorer.py        # calcule score_info(question) selon §0
├── scoring.py                   # calcule score de chaque offre pour un client
├── alertes.py                   # génère alertes anti-survente / sous-couverture
└── tests/
    ├── test_condition_evaluator.py
    ├── test_trame_runtime.py
    ├── test_question_selector.py    # scénarios "trame courte" à valider
    ├── test_information_scorer.py
    └── test_scoring.py
```

**TDD obligatoire sur `rules_engine`** — c'est le cœur du produit, une régression y détruit toute la valeur.

## 0.5 Endpoints API (contract-first)

```
POST   /api/v1/sessions                          → créer session trame
GET    /api/v1/sessions/{id}                     → état complet session
GET    /api/v1/sessions/{id}/next-question       → prochaine question à afficher
POST   /api/v1/sessions/{id}/answer              → enregistrer réponse + retourner nouvel état
GET    /api/v1/sessions/{id}/recommandations     → top offres scorées avec justifs/alertes
POST   /api/v1/sessions/{id}/finalize            → clôture + génère PDF
WS     /api/v1/sessions/{id}/live                → push temps réel (score, alertes)

GET    /api/v1/catalogue/offres?categorie=mobile → liste offres actives
POST   /api/v1/admin/offres                      → CRUD admin

GET    /api/v1/clients                           → liste clients du conseiller
POST   /api/v1/clients                           → créer client

POST   /api/v1/souscriptions                     → enregistrer souscription
GET    /api/v1/souscriptions/commissions        → suivi commissions
```

## 📋 Livrables Phase 0
- [ ] Migration Alembic complète (tables ci-dessus)
- [ ] Modules `rules_engine/*` avec tests unitaires (couverture > 80%)
- [ ] Endpoints API v1 documentés (OpenAPI auto FastAPI)
- [ ] Seed de données : 1 trame mobile + 20 offres mobiles + 15 règles
- [ ] README `rules_engine/README.md` expliquant le DSL

---

## 🎯 PROMPT CLAUDE CODE — PHASE 0

```
Nous démarrons la Phase 0 du projet IA Conseil. Objectif : poser les fondations
techniques du moteur de trame adaptative et de recommandation, sans UI.

Contexte : lire PLAN_IMPLEMENTATION_4_PHASES.md sections 0.1 à 0.5.

Tâches à réaliser dans cet ordre, une par une, en attendant ma validation
entre chaque étape :

1. Créer la migration Alembic avec toutes les tables de la section 0.1.
   Vérifier qu'elle passe en up ET en down. Ajouter tests d'intégrité.

2. Créer le module rules_engine/condition_evaluator.py qui évalue le DSL
   ({$gt, $lt, $in, $and, $or, $not, ...}) sur un dict de contexte.
   Écrire une suite de tests exhaustive AVANT le code (TDD).
   Cas à couvrir : chaque opérateur, chaînage profond, chemin pointé
   (ex. "reponses.conso_data_go"), valeurs null/manquantes.

3. Créer rules_engine/trame_runtime.py :
   - `next_question(trame_def, reponses) -> Question | None`
   - Applique les `branches.skip`, `branches.insert_after`, `show_if`.
   - Tests : trame en Y (branche mobile roaming), trame avec skip.

4. Créer rules_engine/scoring.py :
   - `score_offres(offres, reponses, regles) -> List[OffreScoree]`
   - Applique règles type='filtre' d'abord (exclusion), puis type='scoring'.
   - Chaque offre reçoit un score 0-100 et une liste de justifications.

5. Créer rules_engine/alertes.py :
   - `generer_alertes(offre, reponses, regles) -> List[Alerte]`
   - Applique règles type='alerte'.
   - Templating {{...}} pour les messages.

6. Créer les endpoints FastAPI listés en 0.5 dans un router `sessions_router.py`.
   Endpoint WebSocket avec Redis pub/sub pour la mise à jour temps réel.

7. Écrire le seed dans scripts/seed_mvp.py :
   - 1 trame mobile complète (JSON de 0.2)
   - 20 offres mobiles réelles (Orange, SFR, Bouygues, Free, Sosh, RED, B&You, Prixtel, YouPrice, Coriolis…)
   - 15 règles de recommandation mobiles (anti-survente, boost petit rouleur, roaming, etc.)

Après chaque tâche : lancer les tests, me montrer la couverture, attendre GO
pour la suivante. Ne pas toucher au frontend pour l'instant.
```

---

# 🟨 PHASE 1 — MVP UTILISABLE : MOBILE + BOX + ÉNERGIE (3-5 semaines)

**Objectif** : Un conseiller peut ouvrir la fiche d'un client, dérouler la trame en direct, voir les recommandations en temps réel, générer le PDF, enregistrer la souscription.

## 1.1 Étendre le catalogue et les trames

- Compléter les trames pour **box internet** et **énergie** (structure identique à la trame mobile).
- Peupler le catalogue :
  - **Mobile** : 30-40 offres actives.
  - **Box** : 20-25 offres (fibre + ADSL + 4G/5G box).
  - **Énergie** : 25-30 offres (élec + gaz + duales).
- Créer 40-60 règles de recommandation supplémentaires (§2, 3 du fichier TRAME_CONSEIL_INTELLIGENTE.md).

## 1.2 Frontend — Layout "Trame Live" (Next.js App Router)

```
app/
├── (auth)/
├── (conseiller)/
│   ├── layout.tsx                    # sidebar conseiller
│   ├── clients/
│   │   ├── page.tsx                  # liste clients
│   │   └── [id]/
│   │       ├── page.tsx              # fiche client
│   │       └── trame/[sessionId]/
│   │           └── page.tsx          # ★ LA VUE PIVOT ★
│   ├── catalogue/
│   └── souscriptions/
```

### Composants clés à créer

```
components/trame/
├── TrameLayout.tsx           # 3 colonnes responsive
├── ProgressTree.tsx          # colonne gauche : arbre progression
├── QuestionCard.tsx          # centre : question actuelle
├── AnswerInput.tsx           # inputs typés (number, select, multi, adresse…)
├── LiveRecommandations.tsx   # colonne droite : top 3 offres live
├── AlertesBanner.tsx         # bandeau alertes rouges
├── EconomieTicker.tsx        # gros chiffre "Économie estimée : 458€/an"
└── SyntheseModal.tsx         # modal fin de trame
```

### UX critique (mode "devant le client")

- **Toggle "Mode présentation"** (bouton en haut à droite) qui masque tous les éléments backoffice (marges de commission, notes internes) et grossit la typo.
- **Curseur "Confidentialité"** qui floute côté client les données perso saisies.
- **Temps réel** : chaque réponse → recalcul instantané des recommandations (WebSocket).
- **Retour arrière** libre à n'importe quelle question.
- **Sauvegarde automatique** toutes les 10s.

## 1.3 Génération PDF synthèse

Utiliser `pdf_engine.py` existant + template Jinja2 :
- Page 1 : synthèse (économie annuelle totale, 3 recommandations phares)
- Pages suivantes : détail par catégorie (situation actuelle vs recommandation, comparatif tableau)
- Page finale : calendrier d'actions + coordonnées conseiller

## 1.4 Sources de données catalogue (démarrer les 3 en parallèle)

### A. APIs partenaires (priorité si dispo)
Créer `offres_engine/adapters/` :
- `bouygues_affilie.py`, `free_affilie.py` (via plateformes comme TradeDoubler, Awin, Effiliation)
- Cron quotidien qui re-sync via `celery-beat` ou `apscheduler`.

### B. Scrapers (source secondaire, encadrer légalement)
```
scrapers/
├── base.py                   # classe BaseScraper avec rate-limit, user-agent, cache
├── mobile/
│   ├── free.py
│   ├── orange.py
│   └── ...
├── box/
├── energie/
│   └── comparateur_medef.py  # (préférer sources officielles CRE)
└── scheduler.py              # orchestration Celery
```
⚠️ **Respect strict robots.txt, TOS, rate-limit 1 req/5s, cache 24h.**
⚠️ **JAMAIS de scraping de données clients d'autres services.**

### C. Saisie manuelle admin
- CRUD offres dans `/admin/catalogue/offres`
- Import CSV en bulk
- Workflow validation : `brouillon → validée → publiée`

## 1.5 Multi-canal (visio / téléphone / physique)

**Même interface web** — la magie tient dans 3 réglages :

1. **URL de session partageable** : `/trame/{sessionId}?view=client` (lecture seule, mode présentation forcé) → le conseiller envoie ce lien au client par SMS avant la visio, ou l'ouvre sur son iPad pour rendez-vous physique.
2. **Mode "conseiller au téléphone"** : layout plus dense, raccourcis clavier pour saisie rapide sans écran partagé.
3. **Notes vocales** (mobile-first) : bouton micro pour dicter notes libres pendant la conversation, transcription Whisper API (Phase 2).

## 📋 Livrables Phase 1
- [ ] Trames box + énergie complètes
- [ ] Catalogue mobile (40) + box (25) + énergie (30) alimenté
- [ ] Vue "Trame Live" fonctionnelle bout-en-bout
- [ ] WebSocket temps réel opérationnel
- [ ] Génération PDF synthèse
- [ ] Enregistrement souscription + tracking commission
- [ ] Cron sync APIs partenaires (min 1 fournisseur par catégorie)
- [ ] 2 scrapers fonctionnels (ex : Free mobile, EDF)
- [ ] CRUD admin catalogue
- [ ] URL session partageable en mode client
- [ ] Tests E2E Playwright sur le parcours complet

---

## 🎯 PROMPT CLAUDE CODE — PHASE 1

```
Phase 1 : construire le MVP utilisateur sur le socle Phase 0.
Lire PLAN_IMPLEMENTATION_4_PHASES.md sections 1.1 à 1.5.

Ordre d'exécution :

ÉTAPE A — Données
  1. Écrire les trames JSON complètes pour "box" et "energie_elec" et
     "energie_gaz" (dérivées de TRAME_CONSEIL_INTELLIGENTE.md §2 et §3).
  2. Étendre le seed : +25 offres box, +30 offres énergie, +40 règles.
  3. Créer tests d'intégration : chaque trame doit générer au moins 3
     recommandations non vides pour 5 profils clients types (fixtures).

ÉTAPE B — Frontend trame live
  4. Créer la route Next.js /conseiller/clients/[id]/trame/[sessionId].
  5. Composant TrameLayout 3 colonnes, mobile-responsive.
  6. Intégrer WebSocket (client Next.js) → mise à jour temps réel
     score + alertes + économie estimée après chaque réponse.
  7. Composants QuestionCard/AnswerInput typés (number, select, boolean,
     multi-select, adresse avec autocomplétion via API adresse.data.gouv.fr).
  8. Mode "Présentation" (toggle) qui masque données backoffice + typo grande.
  9. Autosave toutes les 10s + retour arrière libre.

ÉTAPE C — Sortie
  10. Génération PDF avec pdf_engine (template Jinja2), livrable §1.3.
  11. Enregistrement souscription depuis modal fin de trame + calcul
      commission automatique.

ÉTAPE D — Données live
  12. Scaffold offres_engine/adapters/ avec 1 adapter partenaire fonctionnel
      + Celery-beat cron toutes les 24h.
  13. Scaffold scrapers/ avec 2 scrapers (ex: free.py, edf.py), rate-limit
      1req/5s, cache Redis 24h. Respecter robots.txt strictement.
  14. Interface admin CRUD catalogue (/admin/catalogue), import CSV.

ÉTAPE E — Multi-canal
  15. Vue lecture-seule /trame/[id]?view=client (mode présentation forcé,
      pas d'auth requise, token signé courte durée).

ÉTAPE F — Qualité
  16. Tests E2E Playwright : parcours complet mobile (créer client →
      dérouler trame → obtenir reco → générer PDF → souscription).
  17. Documenter la vue "Trame Live" (screenshot + README court).

Attendre validation entre chaque étape. Signaler tout risque
(perf WebSocket, quota API partenaire, légalité scraper).
```

---

# 🟧 PHASE 2 — INTELLIGENCE (4-6 semaines)

**Objectif** : Passer d'un outil "questionnaire + reco" à un outil "conseiller augmenté" qui alerte, veille, relance et cross-sell.

## 2.1 Alertes proactives temps réel (moteur d'événements)

Créer `alertes_engine/` :

- **Anti-survente bloquante** : impossible de finaliser une souscription si alerte critique non levée par le conseiller (double confirmation avec justification écrite → audité).
- **Sous-couverture** : ex. tiers auto sur voiture < 3 ans → alerte de niveau "attention".
- **Meilleur choix alternatif ignoré** : si le conseiller sélectionne l'offre #3 alors que l'offre #1 économise 30€/mois de plus, popup "Confirmer ?".

## 2.2 Veille prix automatisée

`veille_prix_engine.py` (existe déjà — à étendre) :
- Chaque nuit : refresh catalogue.
- Pour chaque **souscription active**, comparer avec les nouvelles offres du marché sur la même catégorie.
- Si nouvelle offre > 15% économie ET fin d'engagement dans < 60 jours → générer une notification conseiller + email pré-rédigé pour le client.

## 2.3 Calendrier & relances automatisées

Nouvelle table `evenement_planifie` :
```sql
CREATE TABLE evenement_planifie (
    id UUID PRIMARY KEY,
    client_id UUID REFERENCES client(id),
    conseiller_id UUID REFERENCES utilisateur(id),
    type TEXT,  -- 'fin_engagement_J-60' | 'bilan_annuel' | 'nps_j30' | 'veille_alerte'
    date_prevue DATE,
    payload JSONB,
    execute BOOLEAN DEFAULT false
);
```

Worker Celery quotidien qui balaie `WHERE date_prevue <= today AND NOT execute`.

## 2.4 Cross-sell inter-catégories

Règles supplémentaires exploitant les réponses de plusieurs trames du même client :
- Si mobile + box séparés chez opérateurs différents → simuler offre convergente.
- Si voyage UE fréquent (déclaré en mobile) → proposer AV voyage annuelle.
- Si conso élec forte + télétravail (déclaré en énergie) → orienter vers rénovation.

Créer `cross_sell_engine.py` qui tourne à la fin de chaque session.

## 2.5 Dashboard conseiller enrichi

Nouveaux widgets :
- **Économies générées YTD** (par client, par catégorie).
- **Pipeline souscriptions** (kanban : en attente → active).
- **Alertes clients** (fin d'engagement, veille prix, NPS).
- **Commissions prévues vs encaissées** (chart mensuel).

## 2.6 Détection biais commercial (garde-fou éthique du modèle commission)

Comme le modèle est basé sur commission % :
- **Audit interne** : chaque session logge la commission de l'offre recommandée.
- **Alerte anti-biais** : si un conseiller recommande systématiquement les offres à plus forte commission alors que d'autres offres scorent mieux → notif superviseur.
- **Reporting** : distribution des recommandations par offre / par conseiller, benchmark équipe.

## 📋 Livrables Phase 2
- [ ] Moteur d'alertes avec 3 niveaux (info / attention / critique)
- [ ] Blocage souscription sur alerte critique (avec override justifié)
- [ ] Veille prix quotidienne opérationnelle
- [ ] Notifications email/SMS automatiques (fin engagement, veille, NPS)
- [ ] Cross-sell engine + suggestions dans UI
- [ ] Dashboard enrichi
- [ ] Audit anti-biais commercial

---

## 🎯 PROMPT CLAUDE CODE — PHASE 2

```
Phase 2 : couche "intelligence" par-dessus le MVP.
Lire PLAN_IMPLEMENTATION_4_PHASES.md sections 2.1 à 2.6.

Ordre :

1. Créer alertes_engine/ avec 3 niveaux (info/attention/critique).
   - Intégration UI : bandeau rouge bloquant si critique non levée.
   - Endpoint POST /sessions/{id}/override-alerte avec justification obligatoire.

2. Étendre veille_prix_engine.py :
   - Job Celery nocturne parcourt souscriptions actives.
   - Détecte offres alternatives >15% économie, engagement compatible.
   - Génère evenement_planifie + notif conseiller.

3. Table evenement_planifie + worker quotidien qui exécute les événements
   (envoi email/SMS via engines existants, création tâche conseiller).

4. cross_sell_engine.py : règles inter-catégories, retourne suggestions
   affichées en fin de session + dans fiche client.

5. Refonte dashboard conseiller avec widgets §2.5 (utiliser Recharts).

6. Anti-biais commercial :
   - Chaque recommandation logge {score, commission, rang}.
   - Rapport hebdo par conseiller (ratio "offre à + forte commission recommandée"
     vs "meilleure offre scorée recommandée").
   - Alerte superviseur si écart > seuil configurable.

7. Tests : simuler 3 mois d'activité (fixtures), vérifier que veille,
   relances et cross-sell se déclenchent aux bons moments.

Validation étape par étape. Signaler tout impact perf sur la DB
(prévoir index si nécessaire).
```

---

# 🟥 PHASE 3 — IA AUTONOME (6-10 semaines)

**Objectif** : L'IA prend en charge les tâches à faible valeur ajoutée (saisie facture, veille marché, rédaction) pour que le conseiller se concentre sur la relation client.

## 3.1 OCR & extraction factures

Pipeline `agents/facture_parser/` :
1. Client upload facture (PDF/JPG) → S3.
2. OCR (Tesseract local ou AWS Textract selon volume).
3. **Extraction structurée par LLM** (Claude API) avec schéma pydantic :
   ```python
   class FactureMobile(BaseModel):
       operateur: str
       forfait_nom: str
       prix_ht: float
       prix_ttc: float
       data_incluse_go: int
       data_consommee_moyenne_go: float
       fin_engagement: date | None
       options: list[str]
   ```
4. Auto-remplissage des réponses de trame → gain 5-10 minutes par rendez-vous.
5. Conseiller valide/corrige avant de continuer.

## 3.2 Copilote conseiller (agent temps réel)

Agent qui tourne en arrière-plan pendant la session :
- **Suggère la prochaine question** la plus impactante (au lieu de suivre strictement l'ordre).
- **Détecte incohérences** ("Le client dit 8 Go mais la facture indique 45 Go — vérifier").
- **Propose formulations** ("Client sceptique sur le changement → suggestion : 'Vous restez libre de résilier à tout moment…'").

Implémentation : sidebar rétractable "IA Assistante" avec streaming réponses Claude.

## 3.3 Génération synthèse PDF en langage naturel

Au lieu du template Jinja2 rigide, LLM rédige :
- Un paragraphe personnalisé par client ("Bonjour M. Dupont, suite à notre échange…").
- Justification économique en langage naturel ("En passant de votre forfait actuel à X, vous économisez Y sur 12 mois principalement parce que…").

Template hybride : structure fixe + zones LLM.

## 3.4 Agent de veille marché autonome

Une fois par semaine :
- Scan des sites concurrents, blogs comparateurs, communiqués opérateurs.
- Détection nouvelles offres non encore en catalogue.
- Rapport hebdo au super-admin : "5 nouvelles offres détectées cette semaine, 2 en promo forte, à intégrer".

Peut utiliser un agent Claude avec outils (WebSearch, WebFetch).

## 3.5 Prévision de churn et scoring client

Modèle ML simple (scikit-learn) prédisant :
- Probabilité qu'un client résilie avant fin d'engagement.
- Probabilité de convertir sur un cross-sell donné.
- Segmentation automatique (économe / premium / éthique / infidèle).

Feed le dashboard conseiller avec priorités d'action.

## 📋 Livrables Phase 3
- [ ] Pipeline OCR facture + extraction LLM structurée
- [ ] Auto-remplissage trame depuis facture
- [ ] Copilote temps réel intégré à l'UI trame
- [ ] Synthèse PDF hybride (template + LLM)
- [ ] Agent veille marché hebdomadaire
- [ ] Modèle churn + scoring client
- [ ] Documentation prompts LLM versionnés dans repo

---

## 🎯 PROMPT CLAUDE CODE — PHASE 3

```
Phase 3 : couche IA autonome.
Lire PLAN_IMPLEMENTATION_4_PHASES.md sections 3.1 à 3.5.

Prérequis : clé API Anthropic dans .env, budget mensuel défini.

Ordre :

1. Pipeline OCR facture (§3.1) :
   - Endpoint POST /clients/{id}/factures/upload
   - Worker Celery : Textract/Tesseract → LLM avec schéma pydantic
   - Test avec 10 factures mobile réelles anonymisées.
   - Fallback manuel si LLM échoue à extraire.

2. Copilote conseiller (§3.2) :
   - Sidebar Next.js "IA Assistante" avec streaming SSE.
   - Endpoint POST /sessions/{id}/copilot avec contexte {réponses, offres candidates}.
   - 3 modes : suggestion question, détection incohérence, aide reformulation.
   - Prompts versionnés dans prompts/copilot/*.md.

3. Synthèse PDF hybride (§3.3) :
   - Refactor pdf_engine : sections template + zones LLM.
   - Cache réponses LLM par session (idempotent).

4. Agent veille marché (§3.4) :
   - Job hebdo, agent Claude avec tools WebSearch/WebFetch.
   - Rapport JSON structuré → mail super-admin + admin UI.
   - Human-in-the-loop : validation avant intégration catalogue.

5. Modèle churn (§3.5) :
   - Features engineering depuis souscription/session/reponses.
   - scikit-learn RandomForest baseline, MLflow pour tracking.
   - Endpoint /clients/{id}/scores → probas + segmentation.

Monitoring impératif : coûts LLM par session (tag Anthropic), alerte
si dépassement seuil. Documenter chaque prompt et son eval.
```

---

# 🧭 RÉCAPITULATIF DE LA ROADMAP

| Phase | Durée | Livrable clé | Valeur pour toi |
|-------|-------|--------------|-----------------|
| **0** | 1-2 sem | Moteur de règles + DB + APIs | Le socle qui rend tout le reste possible |
| **1** | 3-5 sem | MVP utilisable (trame live 3 catégories) | Tu peux démarrer les rendez-vous conseillers |
| **2** | 4-6 sem | Alertes, veille, cross-sell, dashboards | Récurrence de revenu, moins d'oubli, plus de qualité |
| **3** | 6-10 sem | IA autonome (OCR, copilote, veille marché) | Gain de temps massif, différenciation forte |

**Total** : 14 à 23 semaines de dev focused. Avec Claude Code en co-pilote, viser 3-4 mois.

---

# ✅ DÉCISIONS FIGÉES (validées avec Raphaël)

| Décision | Choix retenu |
|----------|--------------|
| Périmètre MVP | Mobile + Box + Énergie |
| Sources catalogue | APIs partenaires + Scrapers légaux + Saisie manuelle admin |
| Rémunération | Commission % sur souscription (garde-fou anti-biais §2.6 obligatoire) |
| Statut légal MVP | Apport d'affaires, pas d'ORIAS requis |
| UX principe #1 | Escargot adaptatif — minimum de questions, audit en < 20 min |
| Multi-canal | Visio + téléphone + physique, même URL web responsive |
| Base de données | **PostgreSQL 15** (déjà dans le stack) |
| Hébergement cible | À choisir en fin de Phase 1 (recommandation : Scaleway ou OVH pour souveraineté RGPD FR) |

---

# 🎬 MASTER PROMPT — À COLLER DANS CLAUDE CODE POUR TOUT LANCER

Copie-colle ce prompt tel quel dans Claude Code au démarrage du repo :

```
Nous démarrons l'implémentation complète du projet IA Conseil selon
PLAN_IMPLEMENTATION_4_PHASES.md (à lire intégralement AVANT toute action).

Stack figée : Next.js 14 (App Router) + FastAPI + PostgreSQL 15 + Redis
+ Celery + SQLAlchemy/Alembic + Sentry (déjà présent).

Principe UX absolu : ESCARGOT ADAPTATIF (§principe #1). Le moteur ne
présente jamais toutes les questions ; il choisit dynamiquement la
prochaine question à plus fort score d'information et arrête la trame
dès qu'un audit complet est possible. Cible < 20 min pour 3 catégories.

Modèle éco = commission → GARDE-FOU ANTI-BIAIS §2.6 obligatoire dès
la Phase 2. Chaque recommandation logge son montant de commission ;
tout écart systématique entre "meilleure offre scorée" et "offre
recommandée en pratique" doit remonter en alerte superviseur.

Exécution :
  1. Commencer par la Phase 0 (§Phase 0) — SANS UI, uniquement DB +
     moteur de règles + endpoints API.
  2. Chaque phase se déroule étape par étape ; me demander validation
     entre chaque étape numérotée (A/B/C…) avant de continuer.
  3. TDD sur rules_engine/ obligatoire (couverture > 80%).
  4. Après chaque étape : lancer les tests, montrer le résultat,
     signaler tout risque ou choix architectural non trivial.
  5. Ne jamais installer une lib sans justifier ; préférer stdlib
     quand possible.
  6. Documenter chaque module dans un README court.
  7. Commit git après chaque étape validée, message clair et scopé.

Prompts détaillés par phase disponibles dans le document
(§"PROMPT CLAUDE CODE — PHASE X").

Démarre par la Phase 0, étape 1 (migration Alembic du schéma DB
§0.1 + §0.1.bis). Je valide, puis on enchaîne.
```

---

# 🧾 CHECKLIST DE VÉRIFICATION AVANT ENVOI À CLAUDE CODE

- [x] Périmètre MVP clair (mobile + box + énergie)
- [x] Stack technique figée (Postgres + FastAPI + Next.js)
- [x] Principe escargot documenté avec formule de scoring
- [x] Schéma DB complet fourni (SQL prêt)
- [x] Format trame + règles en JSON documenté
- [x] Modules Python listés avec responsabilités
- [x] Endpoints API listés
- [x] Garde-fou anti-biais spécifié (§2.6)
- [x] Multi-canal traité (URL partageable, mode présentation)
- [x] Roadmap 4 phases avec livrables par phase
- [x] Prompt Claude Code par phase + master prompt d'entrée
- [x] Décisions figées listées explicitement

**Le plan est prêt. Tu peux copier le "Master Prompt" ci-dessus dans Claude Code, en joignant ce fichier + TRAME_CONSEIL_INTELLIGENTE.md au repo. Claude Code aura tout ce qu'il faut pour démarrer.**
