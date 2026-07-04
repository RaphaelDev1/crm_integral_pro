# IA Conseil — Roadmap & Plan d'Action Complet

**Date :** 03/07/2026
**Statut :** Document de travail — à cocher au fur et à mesure
## PHASE 4 — Intelligence artificielle avancée (Mois 3-4)

### 4.1 — Chatbot client en façade
- **Impact :** 🟠 Fort — acquisition de leads 24/7
- **Effort :** 🏗️ 1-2 semaines
- **Statut :** ✅ Fait

**Quoi :** Un chatbot sur votre site web (ou WhatsApp Business) qui fait le diagnostic initial avec le client, collecte ses infos, et crée un prospect pré-qualifié dans le CRM. Le conseiller n'a plus qu'à appeler avec toutes les données.

**Tâches :**
- ✅ API FastAPI exposant les endpoints : créer prospect, comparer offres, générer bilan (`src/chatbot_api.py`)
- ✅ Frontend chatbot (widget JS à intégrer sur n'importe quel site) (`src/static/chatbot_widget.js`)
- ✅ Prompt Claude pour le parcours conversationnel (collecte progressive des infos) (`src/chatbot_engine.py`)
- ✅ Création automatique du prospect dans le CRM à la fin de la conversation
- ✅ Notification au conseiller assigné (email/Telegram, `notifications.notifier_nouveau_prospect_chatbot`)

---

### 4.2 — Analyse intelligente du marché
- **Impact :** 🟡 Moyen — avantage concurrentiel
- **Effort :** 🏗️ 1-2 semaines
- **Statut :** ✅ Fait

**Quoi :** Un scraper qui surveille les prix des opérateurs et met à jour le catalogue automatiquement. Plus besoin de saisir manuellement les offres.

**Tâches :**
- ✅ Scraper les pages tarifs des principaux opérateurs (Playwright + parsing regex du prix, `src/veille_prix_engine.py`)
- ✅ Détection des changements de prix → alerte admin (table `veille_alertes` + `notifications.notifier_changement_prix`)
- ✅ Mise à jour automatique du catalogue (avec validation admin avant publication) — `valider_alerte()` / `rejeter_alerte()`, onglet **Admin > 📈 Veille prix**
- ✅ Historique des prix pour montrer les tendances au client (table `veille_historique_prix`, graphique dans l'onglet Admin)

---

### 4.3 — API REST complète (découplage Streamlit)
- **Impact :** 🟠 Fort — scalabilité
- **Effort :** 🏗️ 2 semaines
- **Statut :** ✅ Fait

**Quoi :** Extraire toute la logique métier dans une API FastAPI. Streamlit devient un simple frontend. Ça permet ensuite d'avoir une app mobile, un portail client, des webhooks.

**Tâches :**
- ✅ FastAPI avec les endpoints CRUD (prospects, clients, contrats, offres) — `src/crm_api.py`
- ✅ Endpoint diagnostic complet (POST données client → GET recommandations) — `/diagnostic/comparer`, `/diagnostic/bilan`, `/diagnostic/complet`
- ✅ Auth JWT (émis par `jwt_auth.py` au login Streamlit, sans remplacer la session Streamlit elle-même — voir note ci-dessous)
- ✅ Streamlit appelle l'API au lieu de la BDD directement — `src/api_client.py`, avec repli automatique et transparent sur les modules `*_engine.py` si l'API n'est pas démarrée (on reste en phase de test, ce filet de sécurité évite de casser l'appli)
- ✅ Documentation Swagger auto-générée — `http://localhost:8000/docs` une fois `uvicorn crm_api:app --port 8000` lancé

**Note d'implémentation :** la session Streamlit (login par formulaire, `st.session_state`) est conservée telle quelle pour l'UX interne — au moment du login, un JWT est émis localement (sans appel réseau) et stocké en session pour authentifier les appels à l'API. C'est cette API JWT qui sert de point d'entrée pour toute intégration future (mobile, portail, webhooks), sans risque de régression sur le CRM existant.

---

## PHASE 5 — Scale & Vision (Mois 5+)

### 5.1 — App mobile conseiller
- ☐ React Native ou Flutter
- ☐ Photo facture → OCR Vision → diagnostic instantané
- ☐ Mode hors-ligne (sync quand réseau disponible)

### 5.2 — Portail client self-service
- ☐ Le client suit ses contrats, ses économies, ses échéances
- ☐ Reçoit des alertes quand une meilleure offre est disponible
- ☐ Peut lancer un nouveau diagnostic seul

### 5.3 — Multi-tenant (SaaS pour d'autres cabinets)
- ☐ Isolation des données par cabinet
- ☐ Personnalisation (logo, couleurs, catalogue propre)
- ☐ Facturation par cabinet (Stripe)

### 5.4 — Agent IA autonome (la vision finale)
- ☐ Le client upload sa facture
- ☐ L'IA analyse, compare, recommande, souscrit (avec validation)
- ☐ Suivi automatique complet du cycle de vie du contrat
- ☐ Zéro intervention humaine sauf cas complexes

---

## Résumé visuel des priorités

```
SEMAINE 1-2 (faire maintenant)
├── 1.1 Liens affiliés              ⚡ 2-3h    → Revenus immédiats
├── 1.2 Cache Streamlit             ⚡ 30min   → App plus fluide
├── 1.3 Notifications relances      🔧 1j      → Conseillers proactifs
├── 1.4 OCR Vision factures         🔧 1-2j    → Wow effect terrain
└── 1.5 Recherche FTS5              ⚡ 2-3h    → Recherche instantanée

SEMAINE 3-4 (solidifier)
├── 2.1 Refactoring modules         🔧 2-3j    → Code maintenable
├── 2.2 Tests automatisés           🔧 2j      → Fiabilité
├── 2.3 PostgreSQL                  🔧 2-3j    → Concurrence réelle
└── 2.4 Scoring prospects           ✅ Fait    → Priorisation business

MOIS 2 (automatiser)
├── 3.1 Pré-remplissage formulaires 🏗️ 1-2sem  → 5-10min gagnées/souscription
├── 3.2 API opérateurs partenaires  🏔️ variable → Souscription 1-clic
└── 3.3 Suivi post-souscription     🔧 2-3j    → Fidélisation automatique

MOIS 3-4 (intelligence)
├── 4.1 Chatbot client              🏗️ 1-2sem  → Leads 24/7
├── 4.2 Veille prix automatique     🏗️ 1-2sem  → Catalogue toujours à jour
└── 4.3 API REST FastAPI            🏗️ 2sem    → Architecture scalable

MOIS 5+ (scale)
├── 5.1 App mobile                  🏔️         → Mobilité terrain
├── 5.2 Portail client              🏔️         → Self-service
├── 5.3 Multi-tenant SaaS           🏔️         → Nouveau business model
└── 5.4 Agent IA autonome           🏔️         → La vision finale
```

---

## Prochaine action concrète

Ouvrir `app.py` et commencer par la tâche **1.1 (liens affiliés)** — 2-3 heures de travail pour un impact business immédiat.

Dire à Claude : *"On attaque la tâche 1.1 — ajoute les liens de souscription affiliés au catalogue et à l'étape 4 du diagnostic."*
