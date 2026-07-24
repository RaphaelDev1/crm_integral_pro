# IA Conseil — Guide d'utilisation complet

**Mise à jour :** 24/07/2026

Ce document rassemble **toutes les commandes** nécessaires pour installer, lancer et utiliser IA Conseil de bout en bout : l'app Streamlit (`src/`), l'API CRM interne (JWT, désormais sur le port **8003**), l'API chatbot publique **et le portail prospect** (lien personnel facture/test de débit), les scripts planifiés (relances, veille prix), l'envoi de SMS, les tests, la CI, **le backend FastAPI + Postgres (`backend/`, branché sur un vrai Postgres Neon, consommé depuis Streamlit pour les dossiers/mandats/facture LLM — voir §12)** et **le portail client Next.js (`frontend-portail/`, consomme ce backend en HTTP — voir §12.6)**. Pour la description fonctionnelle complète (ce que fait l'app, page par page), voir `IA.CONSEIL.MD`. Pour l'état d'avancement réel du projet et les prochaines tâches, voir `ROADMAP_EXECUTION.md` et `SETUP_STATUS.md`.

---

## 1. Prérequis

- **Python 3.11** (version utilisée en CI — une version 3.10+ convient en local).
- **pip** à jour.
- Optionnel mais recommandé : un environnement virtuel (`venv`).
- Navigateur Chromium pour Playwright (souscription assistée + veille prix) — installé séparément (voir §2).
- Optionnel : une **clé API Anthropic** (OCR Vision + chatbot + analyse facture LLM), un **compte SMTP** (emails), un **bot Telegram** (notifications), un **compte SMS OVH ou Twilio** (envoi du lien « transmettre facture + test de débit », voir §5.5).
- Optionnel (uniquement pour le backend FastAPI/Postgres, §12) : un **Postgres** (Neon ou local), un **Redis** (Celery), un bucket **S3** (Scaleway Object Storage recommandé — upload de documents client).
- Optionnel (uniquement pour le portail client Next.js, §12.6) : **Node.js 18+** et **npm**.

---

## 2. Installation (une seule fois)

```bash
git clone <votre-repo>              # si ce n'est pas déjà fait
cd cmr_integral_pro/src

# Environnement virtuel (recommandé)
python -m venv .venv
# Windows :
.venv\Scripts\activate
# macOS/Linux :
source .venv/bin/activate

# Dépendances applicatives
pip install -r requirements.txt

# Dépendances de test (en plus des précédentes)
pip install -r requirements-dev.txt

# Navigateur Chromium pour Playwright (souscription assistée + veille prix)
playwright install chromium
```

Dépendances installées par `requirements.txt` : `streamlit`, `pandas`, `PyPDF2`, `fpdf2`, `openpyxl`, `anthropic`, `playwright`, `fastapi`, `uvicorn`, `pyjwt`, `requests`, `python-dotenv`, `python-multipart`.

---

## 3. Lancer l'application principale (Streamlit)

```bash
cd src
streamlit run app.py
```

- Ouvre automatiquement `http://localhost:8501`.
- **Premier lancement** : un compte admin est créé automatiquement.
  - Identifiant : `admin`
  - Mot de passe : **généré aléatoirement**, affiché **une seule fois** à l'écran de connexion — à noter immédiatement (il ne sera plus jamais réaffiché en clair).
  - Le **changement de mot de passe est exigé** dès la première connexion (écran bloquant, 8 caractères minimum) — pas besoin d'aller le changer manuellement dans Admin, c'est imposé automatiquement.
- **Anti-bruteforce** : 5 échecs de connexion consécutifs (même identifiant + même IP) bloquent les tentatives pendant 15 minutes (`auth.authentifier_avec_limite`, table `login_tentatives`). Un message précise le temps d'attente restant.
- La base SQLite (`src/ia_conseil_crm.db`) est créée et migrée automatiquement au démarrage — aucune commande manuelle requise, y compris lors des mises à jour du code.
- Arrêter le serveur : `Ctrl+C` dans le terminal.

### Créer d'autres comptes
Une fois connecté en Admin : **🛠️ Admin > 👤 Utilisateurs > ➕ Créer un compte** (rôles disponibles : `Admin`, `Conseiller`, `Lecture`).

### Charger un catalogue de démonstration
**🛠️ Admin > ⚡ Pré-remplir (démo)** — insère un jeu d'offres Télécom/Énergie/Abonnements type, pour tester rapidement le diagnostic sans saisir un catalogue à la main.

---

## 4. API CRM interne (`crm_api.py`) — JWT, intégrations internes/futures

Process **indépendant** de Streamlit, protégé par authentification JWT. Streamlit s'y connecte déjà automatiquement (voir §4.3) mais l'app fonctionne aussi sans elle (repli sur accès direct à la base).

### 4.1 Lancer l'API
```bash
cd src
uvicorn crm_api:app --host 0.0.0.0 --port 8003
```
- Documentation interactive (Swagger) : `http://localhost:8003/docs`
- Endpoint de santé : `http://localhost:8003/health`
- Port **8003** (et non 8000) : `backend/` (FastAPI + Postgres, §12) occupe le port 8000 et n'implémente ni `/contrats` ni `/offres` — les deux projets sont volontairement isolés et peuvent tourner en même temps sans conflit.

### 4.2 Variables d'environnement
Copier `src/.env.example` en `src/.env` (déjà gitignored) et remplir les valeurs — ce fichier prend désormais le pas sur les réglages saisis dans l'UI Admin (voir `src/secrets_config.py` : `.env` prioritaire, repli sur la base tant qu'une variable n'est pas définie, pour ne rien casser sur une instance existante).

| Variable | Rôle | Défaut si absente |
|---|---|---|
| `APP_ENV` | `development` (défaut) ou `production` | `development` |
| `CRM_API_SECRET` | Secret de signature des JWT — **obligatoire si `APP_ENV=production`** (l'API refuse de démarrer sans lui) | Secret de développement (avertissement affiché) hors production |
| `CRM_API_URL` | URL de `crm_api.py` utilisée par Streamlit (`api_client.py`) | `http://127.0.0.1:8003` |
| `CRM_API_TIMEOUT` | Timeout (secondes) des appels Streamlit → `crm_api.py` | `3` |
| `BACKEND_API_URL` | URL de `backend/main.py` (Postgres — dossiers, mandats d'honoraires, analyse de facture LLM), utilisée par `api_client.py`. Aucun repli local : sans ce service lancé, ces fonctions affichent un message clair au conseiller | `http://127.0.0.1:8000` |
| `SMTP_SERVEUR`/`SMTP_PORT`/`SMTP_USER`/`SMTP_MDP`/`SMTP_EXPEDITEUR` | Config SMTP (sinon ressaisie dans Admin > Email, stockée en base) | — |
| `ANTHROPIC_API_KEY` | Clé Claude (OCR Vision, chatbot, analyse facture LLM) | — |
| `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` | Notifications Telegram | — |
| `SMS_PROVIDER`, `OVH_*`, `TWILIO_*` | Envoi SMS (lien documents prospect) — voir §5.5 | `SMS_PROVIDER=ovh` |
| `PORTAIL_PROSPECT_BASE_URL` | Base publique de la mini-page portail prospect (servie par `chatbot_api.py`) — voir §5.5 | `http://127.0.0.1:8001` |

Générer un secret : `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Exemple (Windows, PowerShell) :
```powershell
$env:CRM_API_SECRET = "un-secret-long-et-aleatoire"
uvicorn crm_api:app --host 0.0.0.0 --port 8003
```
Exemple (bash) :
```bash
export CRM_API_SECRET="un-secret-long-et-aleatoire"
uvicorn crm_api:app --host 0.0.0.0 --port 8003
```

### 4.3 Utiliser l'API (exemples `curl`)
```bash
# 1. Se connecter (même identifiants que Streamlit — mot de passe généré au
#    premier lancement, cf. §3) → récupérer un token
curl -X POST http://localhost:8003/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<votre-mot-de-passe>"}'
# → {"access_token": "...", "token_type": "bearer", "user": {...}}

# 2. Appeler un endpoint protégé avec le token
curl http://localhost:8003/prospects \
  -H "Authorization: Bearer <token>"

# 3. Créer un prospect (rôle Conseiller ou Admin requis)
curl -X POST http://localhost:8003/prospects \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"prenom":"Jean","nom":"Dupont","ville":"Lyon","cout_mensuel_actuel":45.0}'

# 4. Comparer des offres (diagnostic, authentifié, sans limite de débit)
curl -X POST http://localhost:8003/diagnostic/comparer \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"univers":"Télécom","categorie":"Mobile","cout_actuel_mensuel":29.99}'
```

Routes disponibles (résumé) :
- `POST /auth/login`, `GET /auth/me`
- `GET/POST/PATCH/DELETE /prospects`, `/prospects/{id}`
- `GET/POST/PATCH/DELETE /clients`, `/clients/{id}`
- `GET/POST /clients/{id}/contrats`, `PATCH/DELETE /contrats/{id}`
- `GET/POST/PATCH/DELETE /offres`, `/offres/{id}` (écriture réservée Admin)
- `POST /diagnostic/comparer`, `/diagnostic/bilan`, `/diagnostic/complet`
- `GET /health`

### 4.4 Lien avec Streamlit
`app.py` appelle désormais `api_client.py` (mêmes signatures que les modules `*_engine.py`). Si l'API n'est pas lancée, ou injoignable, Streamlit **retombe automatiquement** sur l'accès direct à la base — un message `⚠️ API CRM interne injoignable` s'affiche une seule fois par session, sans bloquer l'usage. **Vous n'êtes donc jamais obligé de lancer `crm_api.py` pour utiliser l'application au quotidien.**

> ℹ️ En usage courant (`streamlit run app.py` seul, sans lancer `crm_api.py` en parallèle), ce message apparaît **systématiquement** au premier chargement — c'est normal et sans gravité, pas un bug : lancez `crm_api.py` en plus (§4.1) uniquement si vous voulez faire disparaître l'avertissement ou utiliser l'API pour une intégration externe.

---

## 5. API chatbot publique (`chatbot_api.py`) — diagnostic 24/7, sans authentification

Process indépendant, destiné à être exposé sur un site web public (widget de chat) ou intégré à un futur canal (WhatsApp...). **Contrairement à `crm_api.py`, ces endpoints ne sont pas authentifiés** (usage public assumé), mais sont protégés par un rate-limit basique (30 req/min/IP).

### 5.1 Lancer l'API chatbot
```bash
cd src
uvicorn chatbot_api:app --host 0.0.0.0 --port 8001
```
- Documentation Swagger : `http://localhost:8001/docs`

### 5.2 Configurer la clé Claude (obligatoire pour le chatbot conversationnel)
Dans Streamlit : **🛠️ Admin > 🔍 OCR Vision** → saisir la clé API Anthropic (stockée en base, table `parametres`, jamais affichée en clair). Cette même clé sert à l'OCR Vision des factures ET au chatbot.

### 5.3 Endpoints
```bash
# Faire progresser une conversation
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"abc123","message":"Bonjour, je veux réduire ma facture mobile"}'

# Endpoints structurés (réutilisables hors chat)
curl -X POST http://localhost:8001/api/prospects -H "Content-Type: application/json" -d '{...}'
curl -X POST http://localhost:8001/api/offres/comparer -H "Content-Type: application/json" -d '{...}'
curl -X POST http://localhost:8001/api/bilan -H "Content-Type: application/json" -d '{...}'
```
Le chatbot collecte progressivement l'identité, le contact, la ville et la situation Télécom/Énergie, puis crée automatiquement un prospect (`origine='Chatbot'`) et notifie le conseiller (email/Telegram — mêmes réglages que `notifications.py`, section 6).

### 5.4 Intégrer le widget sur un site
```html
<script src="https://votre-domaine/widget/chatbot_widget.js" data-api-url="https://votre-domaine"></script>
```
Bulle de chat flottante, sans dépendance externe (`src/static/chatbot_widget.js`). CORS ouvert à tout domaine pour permettre l'intégration sur n'importe quel site.

### 5.5 Portail prospect — lien personnel « transmettre facture + test de débit »

Servi par ce même process (`chatbot_api.py`), sur `GET /portail/{token}` (`http://localhost:8001/portail/<token>` en local). Depuis la fiche prospect (Streamlit), le conseiller génère ce lien (14 jours de validité) et l'envoie par SMS et/ou email ; le prospect ouvre la page sans authentification autre que le token, et peut transmettre lui-même sa facture et un test de débit (analysés automatiquement), ou télécharger son PDF « aperçu ».

**Configurer l'envoi SMS** (`src/sms_engine.py`, OVH par défaut ou Twilio — mêmes variables que `backend/.env.example`, un compte déjà configuré côté `backend/` peut être réutilisé tel quel) — dans `src/.env` :
```
SMS_PROVIDER=ovh                 # ou "twilio"
OVH_SMS_ENDPOINT=ovh-eu
OVH_SMS_SERVICE_NAME=
OVH_APPLICATION_KEY=
OVH_APPLICATION_SECRET=
OVH_CONSUMER_KEY=
# ou, si SMS_PROVIDER=twilio :
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
```
Sans ces valeurs, le SMS n'est simplement pas envoyé (`sms_engine.envoyer_sms` renvoie `False`, jamais d'exception) — l'email (si un email prospect est renseigné) et le lien affiché au conseiller restent disponibles.

`PORTAIL_PROSPECT_BASE_URL` (défaut `http://127.0.0.1:8001`) doit pointer vers l'URL publique réelle de `chatbot_api.py` une fois déployé, pour que les liens envoyés par SMS/email soient utilisables par le prospect depuis son téléphone.

---

## 6. Notifications planifiées (`notifications.py`)

Script autonome, à exécuter une fois par jour via une tâche planifiée — **indépendant de Streamlit**, la machine n'a pas besoin d'avoir l'app ouverte.

### 6.1 Configurer les destinataires
**🛠️ Admin > 📧 Email** :
- Email du conseiller à notifier.
- SMTP (serveur, port, identifiant, mot de passe) — nécessaire pour les envois email (digest, alertes, teaser client).
- Jeton du bot Telegram + chat ID (optionnel, canal alternatif/complémentaire à l'email).

### 6.2 Lancer manuellement
```bash
cd src
python notifications.py                  # relances du jour + retard + alertes fin d'engagement
python notifications.py --resume-hebdo   # + résumé hebdomadaire (à lancer le lundi)
```
Ce que fait le script :
- Envoie (email et/ou Telegram) la liste des relances prospects + clients du jour et en retard.
- Envoie automatiquement l'alerte de fin d'engagement (email HTML avec offre alternative si une économie a été identifiée) pour tout contrat atteignant le seuil de 60 jours avant échéance, et journalise l'action dans l'audit trail.
- Avec `--resume-hebdo` : ajoute un résumé (nombre de prospects/clients en base, économies totales estimées).

### 6.3 Planifier l'exécution quotidienne

**Windows (Terminal / PowerShell, en administrateur si besoin) :**
```bat
schtasks /create /tn "IA Conseil - Relances" /sc daily /st 08:00 /tr "python C:\chemin\vers\src\notifications.py"
```

**Linux/macOS (crontab) :**
```bash
crontab -e
# ajouter la ligne :
0 8 * * * cd /chemin/vers/src && python notifications.py
```

---

## 7. Veille prix automatique (`veille_prix_engine.py`)

Script autonome qui scrape (Playwright **headless**) les pages tarifs des opérateurs surveillés et détecte les changements de prix. **Ne modifie jamais le catalogue automatiquement** : chaque changement crée une alerte à valider par un admin.

### 7.1 Configurer les sources à surveiller
Dans Streamlit : **🛠️ Admin > 📈 Veille prix > 🔗 Sources surveillées** :
- Univers / Catégorie / Fournisseur / Nom de l'offre suivie.
- URL de la page tarif à surveiller.
- Sélecteur CSS du prix (clic droit > Inspecter sur la page cible pour le trouver).
- Offre du catalogue à mettre à jour automatiquement **après validation admin** (optionnel — laisser vide pour une veille concurrentielle sans impact catalogue).

### 7.2 Lancer manuellement
Deux façons équivalentes :
```bash
cd src
python veille_prix_engine.py
```
ou, depuis l'app, bouton **« 🔎 Lancer la veille maintenant »** dans **Admin > 📈 Veille prix > 🔗 Sources surveillées**.

### 7.3 Traiter les alertes détectées
**🛠️ Admin > 📈 Veille prix > 🔔 Alertes en attente** : valider (répercute le nouveau prix sur l'offre liée + journalise dans l'audit) ou rejeter chaque changement détecté.
**📊 Historique des prix** : graphique de tendance par source surveillée.

### 7.4 Planifier l'exécution

**Windows :**
```bat
schtasks /create /tn "IA Conseil - Veille prix" /sc daily /st 07:00 /tr "python C:\chemin\vers\src\veille_prix_engine.py"
```

**Linux/macOS :**
```bash
0 7 * * *   cd /chemin/vers/src && python veille_prix_engine.py
```

---

## 8. Souscription assistée (Playwright, dans l'UI Streamlit)

Aucune commande à lancer séparément : le bouton **« 🖊️ Pré-remplir la souscription »** (fiche prospect, fiche client/contrat — affiché dès qu'une offre a un lien de souscription, automatisé pour les opérateurs **Free** et **Bouygues**) ouvre directement, depuis l'app, un navigateur Chromium **visible** et pré-rempli avec les coordonnées du client. Chez **Free**, le test d'éligibilité par adresse et le choix de la box correspondant à l'offre du catalogue sont remplis automatiquement en plus des coordonnées. Le conseiller vérifie et valide lui-même sur le site — **rien n'est jamais soumis automatiquement**.

Prérequis : `playwright install chromium` (voir §2) doit avoir été exécuté au moins une fois sur le poste.

---

## 9. Tests automatisés

### 9.1 Lancer la suite localement
```bash
cd src
pytest -q
```
Couvre : auth, moteur d'offres, utils, pdf_engine, prospects_engine, contrats_engine, souscription_engine, chatbot, notifications, sms_engine (fixtures communes dans `tests/conftest.py`).

### 9.2 Lancer un fichier ou un test précis
```bash
pytest tests/test_offres_engine.py -q
pytest tests/test_offres_engine.py::test_comparer_offres_trie_par_economie -q
```

### 9.3 CI (GitHub Actions)
`.github/workflows/tests.yml` exécute automatiquement, à chaque `push`/`pull request` :
```bash
pip install -r src/requirements-dev.txt
cd src && pytest -q
```
Aucune action manuelle nécessaire — vérifier l'onglet **Actions** du dépôt GitHub pour le statut.

### 9.4 Tests du backend (`backend/tests/`)
Indépendants de la suite `src/` — ne nécessitent **pas** de Postgres réel (client Anthropic et connexion DB mockés) :
```bash
pip install -r backend/requirements.txt
pytest backend/tests -q
```

---

## 10. Récapitulatif — tout lancer en une fois (usage quotidien complet)

Ouvrir 3 terminaux séparés (chacun dans `src/`, environnement virtuel activé) :

```bash
# Terminal 1 — l'application principale (obligatoire)
streamlit run app.py

# Terminal 2 — API CRM interne (optionnelle : Streamlit fonctionne sans, avec repli automatique)
uvicorn crm_api:app --host 0.0.0.0 --port 8003

# Terminal 3 — API chatbot publique (optionnelle : uniquement si le widget de site est utilisé)
uvicorn chatbot_api:app --host 0.0.0.0 --port 8001
```

Et en tâches planifiées (pas de terminal à garder ouvert) :
```bash
python notifications.py        # tous les matins, ex. 08:00
python veille_prix_engine.py   # tous les matins, ex. 07:00
```

Le nouveau backend `backend/` (§12) est **optionnel** vis-à-vis de Streamlit : Streamlit fonctionne en totale autonomie sans lui (il tourne toujours en direct sur SQLite via `db.py`) — ne le lancer que si vous testez explicitement cette brique **ou** le portail client Next.js (`frontend-portail/`), qui lui en dépend entièrement.

### Ports par défaut
| Service | Port | Authentifié ? |
|---|---|---|
| Streamlit (`app.py`) | 8501 | Session login (formulaire) |
| API CRM interne (`crm_api.py`) | 8003 | Oui — JWT |
| API chatbot publique + portail prospect (`chatbot_api.py`) | 8001 | Non (rate-limit 30 req/min/IP ; portail prospect protégé par token) |
| Backend FastAPI + Postgres (`backend.main:app`) | 8000 | JWT (`/dossiers`, `/clients`...) ou token unique (`/portail/*`) |
| Portail client Next.js (`frontend-portail/`) | 3000 | Non (token dans l'URL) |

`crm_api.py` (port 8003) et `backend/main.py` (port 8000) sont deux projets volontairement isolés — plus de conflit de port entre eux. Le portail Next.js (`NEXT_PUBLIC_API_URL`) attend toujours `backend/` sur `http://localhost:8000` par défaut.

---

## 11. Dépannage rapide

| Symptôme | Cause probable | Solution |
|---|---|---|
| Mot de passe admin `Admin2026!` refusé au premier lancement | Depuis le fix sécurité Sprint 1, le mot de passe est **généré aléatoirement**, pas fixe | Relire le mot de passe affiché à l'écran lors du tout premier lancement (il n'est affiché qu'une fois) ; si perdu, supprimer `src/ia_conseil_crm.db` (⚠️ efface toutes les données) ou faire réinitialiser le compte par un autre Admin |
| « Trop de tentatives échouées. Réessayez dans N min. » | 5 échecs de connexion consécutifs (même identifiant + IP) | Attendre le délai indiqué (15 min max), ou vérifier l'identifiant/mot de passe |
| `⚠️ API CRM interne injoignable` dans Streamlit | `crm_api.py` non lancé | Sans gravité, comportement normal en usage courant — Streamlit fonctionne en accès direct base. Lancer l'API (§4) seulement si besoin (intégration externe). |
| OCR Vision inactif / factures lues par regex uniquement | Clé API Anthropic absente | Configurer dans **Admin > 🔍 OCR Vision** ou `ANTHROPIC_API_KEY` dans `src/.env` |
| Bouton pré-remplissage souscription sans effet | Chromium Playwright non installé | `playwright install chromium` |
| Veille prix : « package playwright non installé » | idem | `pip install playwright && playwright install chromium` |
| Emails non envoyés (teaser, alertes, digest) | SMTP non configuré | Renseigner **Admin > 📧 Email** ou `SMTP_*` dans `src/.env` |
| `notifications.py`/`veille_prix_engine.py` : rien ne se passe | Pas de relance/changement de prix ce jour-là | Comportement normal — le script journalise silencieusement s'il n'y a rien à signaler |
| JWT expiré côté API (`crm_api.py`) | Jeton valide 8h | Se reconnecter (`POST /auth/login`) ou redémarrer la session Streamlit |
| Backend `backend/` : `/auth/login`, `/clients`, `/prospects` renvoient 500 | Pas de vrai Postgres derrière `DATABASE_URL` (sur un nouveau clone/poste, `backend/.env` est gitignored et doit être recréé) | Provisionner un Postgres (ex. Neon, offre gratuite), renseigner `backend/.env` → `DATABASE_URL`, puis `alembic upgrade head` (§12) |
| Backend `backend/` sur Neon : erreurs intermittentes `prepared statement does not exist` | Neon expose un endpoint **pooler** (PgBouncer, transaction pooling) incompatible avec le cache de requêtes préparées d'`asyncpg` | Vérifier que `backend/core/database.py` passe bien `connect_args={"statement_cache_size": 0}` à l'engine (déjà fait dans le code fourni) |
| Backend `backend/` : `celery -A backend.workers.celery_app worker` ne démarre pas / tâches jamais exécutées | Redis non lancé | Démarrer un Redis local (`redis-server` ou conteneur Docker) et vérifier `REDIS_URL` dans `backend/.env` |
| Portail Next.js : « Lien invalide » alors que le token vient d'être généré | Backend `backend/` non lancé, ou `NEXT_PUBLIC_API_URL` (`frontend-portail/.env.local`) ne pointe pas vers le bon port | Vérifier `uvicorn backend.main:app` tourne bien sur le port attendu (§12.3) et que `frontend-portail/.env.local` correspond |
| Portail Next.js : upload de document échoue avec « Stockage impossible » | `S3_BUCKET`/`S3_ACCESS_KEY_ID`/`S3_SECRET_ACCESS_KEY` non renseignés dans `backend/.env` | Provisionner un bucket S3 (Scaleway Object Storage recommandé, voir §12.6) |

---

## 12. Backend FastAPI + Postgres (`backend/`) et portail client Next.js (`frontend-portail/`)

**Statut (voir `ROADMAP_EXECUTION.md`, Sprints 2/3/4/5/6) : branché sur un vrai Postgres (Neon), portail client Next.js livré et testé bout-en-bout.** L'auth et le CRUD prospects/clients/contrats/offres de Streamlit continuent de tourner **entièrement en direct sur SQLite** (pas de bascule sur ce backend pour ces opérations) — mais `src/app.py` consomme désormais ce backend **en HTTP** (via `api_client.py`) pour ouvrir un dossier, envoyer le lien du portail client par SMS/email, suivre sa timeline, gérer son mandat d'honoraires, et faire analyser une facture par le LLM du backend. Ces commandes ne sont nécessaires que pour lancer le backend lui-même et/ou le portail client — pas pour l'usage quotidien Streamlit (§1 à §11), qui fonctionne sans lui (avec un message clair au conseiller si ces fonctions sont utilisées alors que le backend n'est pas lancé).

Ce qui est déjà écrit et testé : auth JWT (login/refresh/mot de passe oublié), CRUD `clients`/`prospects`/`dossiers`, briefing client agrégé, machine à états du workflow de souscription, mandat d'honoraires, génération de lien client unique + envoi **réel** par SMS (OVH/Twilio)/email (Resend) + notifications automatiques par statut de dossier + relance quotidienne des dossiers stagnants (Celery beat), portail public (upload documents avec KYC automatique par Claude Vision, suivi de dossier), analyse de facture par LLM, webhook Yousign (signature électronique), tâches asynchrones Celery. Ce qui manque encore : comptes Yousign/S3/Anthropic/OVH/Twilio/Resend **réels** pour tester tout ça en conditions réelles (voir §12.0), chiffrement `pgcrypto` des colonnes PII, script `migrate_sqlite_to_postgres.py`, génération du PDF de mandat et bouton d'envoi en signature côté Streamlit.

### 12.0 Comptes externes à créer

| Service | Sert à | Variable(s) dans `backend/.env` |
|---|---|---|
| **Neon (Postgres)** | Base de données du backend | `DATABASE_URL` |
| **Anthropic** | Analyse LLM factures + validation KYC | `ANTHROPIC_API_KEY` |
| **Yousign** (sandbox puis prod, developers.yousign.com) | Signature électronique du mandat | `YOUSIGN_API_KEY`, `YOUSIGN_WEBHOOK_SECRET` |
| **Scaleway Object Storage** (ou S3 compatible) | Stockage chiffré des documents KYC | `S3_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` |
| **OVH SMS ou Twilio** | Envoi réel du lien client par SMS | `SMS_PROVIDER`, `OVH_*` ou `TWILIO_*` |
| **Resend** (resend.com + domaine d'envoi vérifié) | Emails transactionnels (mandat, docs validés, offre activée) | `RESEND_API_KEY` |
| **Stripe** | Facturation client (abonnement Gestionnaire perso, commissions) — pas bloquant avant la Phase 2 | `STRIPE_*` |
| **Redis** | Broker Celery (KYC async, relances) — `redis-server` local ou managé (Upstash, Redis Cloud) | `REDIS_URL` |

Une fois les comptes créés, compléter `backend/.env` (copier les nouvelles clés depuis `backend/.env.example`, qui liste toutes les variables attendues).

### 12.1 Installation (backend)
```bash
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
# éditer backend/.env : APP_ENV, DATABASE_URL (Postgres), CRM_API_SECRET,
# ANTHROPIC_API_KEY, YOUSIGN_API_KEY/YOUSIGN_API_URL/YOUSIGN_WEBHOOK_SECRET,
# REDIS_URL, PORTAIL_CLIENT_BASE_URL, S3_* (Scaleway), STRIPE_*, SMS_*, RESEND_*
```
Dépendances installées par `backend/requirements.txt` (en plus de `fastapi`/`sqlalchemy`/`alembic`/`celery`) : `boto3` (S3), `stripe`, `resend`, `python-multipart` (upload de fichiers).

### 12.2 Provisionner Postgres et migrer le schéma
```bash
# Ex. Neon (offre gratuite 500 Mo) — récupérer l'URL de connexion, format :
# postgresql+asyncpg://user:password@ep-xxx.neon.tech/ia_conseil
# puis la mettre dans backend/.env → DATABASE_URL
# Si l'URL Neon fournie contient channel_binding=require, le retirer (non supporté par
# asyncpg) ; remplacer sslmode=require par ssl=require.

alembic upgrade head
```
`alembic current` doit ensuite afficher `0006 (head)`. Applique dans l'ordre : `0001` (schéma initial), `0002` (mandats/documents), `0003` (`dossiers`, `tokens_publics`, `commissions`, `abonnements`), `0004` (factures analysées), `0005` (relances dossier), `0006` (mandats d'honoraires).

Si l'URL Postgres pointe vers un endpoint **pooler** (Neon en pooler, PgBouncer...), garder `connect_args={"statement_cache_size": 0}` dans `backend/core/database.py` (déjà présent) pour éviter des erreurs intermittentes `prepared statement does not exist`.

### 12.3 Lancer l'API
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
- Doc Swagger : `http://localhost:8000/docs`
- Santé : `GET /health`
- Port 8000 : `crm_api.py` (§4) tourne désormais par défaut sur 8003, donc plus de conflit entre les deux. Le portail Next.js (§12.6) attend `http://localhost:8000` par défaut.

Endpoints (préfixes) :
- `POST /auth/login`, `/auth/refresh`, `/auth/forgot-password`, `/auth/reset-password`, `GET /auth/me`
- `GET/POST/PUT/DELETE /clients`, `/clients/{id}` + `GET /clients/{id}/briefing` (vue agrégée : infos client + dossier en cours + dernière facture analysée) — JWT requis
- `GET/POST/PUT/DELETE /prospects`, `/prospects/{id}` (JWT requis)
- `GET/POST /dossiers`, `GET/PUT /dossiers/{id}`, `POST /dossiers/{id}/transition`, `GET /dossiers/{id}/timeline`, `POST /dossiers/{id}/notes`, `POST /dossiers/{id}/token-client` (génère le lien unique), `POST /dossiers/{id}/envoyer-lien-client` (l'envoie réellement par SMS ou email) — JWT requis
- `GET/POST /dossiers/{id}/mandat-honoraires`, `POST /dossiers/{id}/mandat-honoraires/marquer-signe` (JWT requis)
- `GET /portail/{token}`, `POST /portail/{token}/documents`, `GET /portail/{token}/suivi` (**pas de JWT** — accès par token unique, consommés par `frontend-portail/`)
- `POST /factures/analyze` (JWT requis — analyse LLM structurée d'une facture PDF, aussi consommée par la fiche client Streamlit)
- `POST /webhooks/yousign` (mise à jour de statut de signature de mandat, signature HMAC vérifiée)

### 12.4 Worker Celery (KYC + signature async + relances planifiées)
Nécessite un Redis lancé (`redis-server` ou Docker) et `REDIS_URL` renseigné dans `backend/.env` :
```bash
celery -A backend.workers.celery_app worker --loglevel=info
celery -A backend.workers.celery_app beat --loglevel=info   # relance quotidienne des dossiers stagnants
```
Tâches du worker : `valider_document_kyc`, `envoyer_mandat_signature`, `telecharger_mandat_signe` (retry automatique en cas d'échec). Note : l'upload d'un document sur le portail client (§12.6) valide déjà le document **de façon synchrone** via `kyc_engine` (retour immédiat au client) — ce worker Celery sert aux validations/re-traitements différés, pas au chemin critique de l'upload.

Le process `beat` planifie quotidiennement (8h00) `relancer_dossiers_stagnants` : envoie un email/SMS de relance (`dossier_notifications.notifier_relance`) pour tout dossier resté au même statut plus longtemps que le seuil défini pour ce statut (`SEUILS_JOURS_PAR_STATUT`, 2 à 10 jours selon l'étape). Sans `beat` lancé, ces relances ne partent pas (le reste du backend fonctionne normalement).

### 12.5 Tests
```bash
pytest backend/tests -q   # mockés (Anthropic, DB) — ne nécessitent pas de Postgres réel
```

### 12.6 Portail client (`frontend-portail/`, Next.js)

Process Node **indépendant**, consomme le backend `backend/` (§12.3) en HTTP. Destiné au **client final** (pas au conseiller) : accès par lien unique, sans compte ni mot de passe.

**Installation :**
```bash
cd frontend-portail
npm install
cp .env.example .env.local   # si .env.local n'existe pas encore — NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Lancer en dev :**
```bash
cd frontend-portail
npm run dev
```
Ouvre `http://localhost:3000`.

**Build production :**
```bash
cd frontend-portail
npm run build
npm start
```

**Générer un lien client de test (workflow complet) :**
```bash
# 1. Backend lancé (§12.3) + un utilisateur connecté (POST /auth/login → access_token)
# 2. Créer un client de test :
curl -X POST http://localhost:8000/clients -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" -d '{"prenom":"Jean","nom":"Dupont", ...}'
# 3. Créer un dossier pour ce client :
curl -X POST http://localhost:8000/dossiers -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" -d '{"client_id": 1, "univers": "telecom_mobile"}'
# 4. Générer le lien unique :
curl -X POST http://localhost:8000/dossiers/1/token-client -H "Authorization: Bearer <token>"
# → {"token": "...", "url": "http://localhost:3000/dossier/<token>", "expire_le": "...", "message_sms_suggere": "..."}
# 5. Ouvrir l'URL renvoyée dans un navigateur (idéalement en navigation privée) : doit
#    afficher le portail client, avec la liste des documents à fournir.
```
L'envoi automatique du lien par SMS/email réel est maintenant possible via `POST /dossiers/{id}/envoyer-lien-client` (§12.3) — sans compte OVH/Twilio/Resend renseigné dans `backend/.env`, il suffit encore de copier-coller l'URL ou le `message_sms_suggere` manuellement au client.

Nécessite pour un test complet d'upload : un bucket S3 configuré (`backend/.env` → `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` — Scaleway Object Storage recommandé) et idéalement une vraie `ANTHROPIC_API_KEY` pour que la validation KYC automatique fonctionne (sinon chaque document uploadé reste en statut `erreur` — reçu mais non validé, sans bloquer l'upload).

---

Pour la description fonctionnelle complète de l'application (pages, workflows métier, schéma de base de données, sécurité), voir **`IA.CONSEIL.MD`**. Pour la feuille de route stratégique d'origine (déjà largement réalisée), voir **`IA_CONSEIL_ROADMAP.md`** ; pour le plan d'exécution actif (sprints en cours, état d'avancement réel) et les tâches restantes, voir **`ROADMAP_EXECUTION.md`** et **`SETUP_STATUS.md`**.
