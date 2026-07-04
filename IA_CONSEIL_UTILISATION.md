# IA Conseil — Guide d'utilisation complet

**Mise à jour :** 04/07/2026

Ce document rassemble **toutes les commandes** nécessaires pour installer, lancer et utiliser IA Conseil de bout en bout : l'app Streamlit, l'API CRM interne (JWT), l'API chatbot publique, les scripts planifiés (relances, veille prix), les tests, et la CI. Pour la description fonctionnelle complète (ce que fait l'app, page par page), voir `IA.CONSEIL.MD`.

---

## 1. Prérequis

- **Python 3.11** (version utilisée en CI — une version 3.10+ convient en local).
- **pip** à jour.
- Optionnel mais recommandé : un environnement virtuel (`venv`).
- Navigateur Chromium pour Playwright (souscription assistée + veille prix) — installé séparément (voir §2).
- Optionnel : une **clé API Anthropic** (OCR Vision + chatbot), un **compte SMTP** (emails), un **bot Telegram** (notifications).

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

Dépendances installées par `requirements.txt` : `streamlit`, `pandas`, `PyPDF2`, `fpdf2`, `openpyxl`, `anthropic`, `playwright`, `fastapi`, `uvicorn`, `pyjwt`, `requests`.

---

## 3. Lancer l'application principale (Streamlit)

```bash
cd src
streamlit run app.py
```

- Ouvre automatiquement `http://localhost:8501`.
- **Premier lancement** : un compte admin est créé automatiquement.
  - Identifiant : `admin`
  - Mot de passe : `Admin2026!`
  - **À changer immédiatement** dans le menu **🛠️ Admin > 👤 Utilisateurs**.
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
uvicorn crm_api:app --host 0.0.0.0 --port 8000
```
- Documentation interactive (Swagger) : `http://localhost:8000/docs`
- Endpoint de santé : `http://localhost:8000/health`

### 4.2 Variables d'environnement
| Variable | Rôle | Défaut si absente |
|---|---|---|
| `CRM_API_SECRET` | Secret de signature des JWT — **à définir avant tout déploiement réel** | Secret de développement (avertissement affiché) |
| `CRM_API_URL` | URL de l'API utilisée par Streamlit (`api_client.py`) | `http://127.0.0.1:8000` |
| `CRM_API_TIMEOUT` | Timeout (secondes) des appels Streamlit → API | `3` |

Exemple (Windows, PowerShell) :
```powershell
$env:CRM_API_SECRET = "un-secret-long-et-aleatoire"
uvicorn crm_api:app --host 0.0.0.0 --port 8000
```
Exemple (bash) :
```bash
export CRM_API_SECRET="un-secret-long-et-aleatoire"
uvicorn crm_api:app --host 0.0.0.0 --port 8000
```

### 4.3 Utiliser l'API (exemples `curl`)
```bash
# 1. Se connecter (même identifiants que Streamlit) → récupérer un token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin2026!"}'
# → {"access_token": "...", "token_type": "bearer", "user": {...}}

# 2. Appeler un endpoint protégé avec le token
curl http://localhost:8000/prospects \
  -H "Authorization: Bearer <token>"

# 3. Créer un prospect (rôle Conseiller ou Admin requis)
curl -X POST http://localhost:8000/prospects \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"prenom":"Jean","nom":"Dupont","ville":"Lyon","cout_mensuel_actuel":45.0}'

# 4. Comparer des offres (diagnostic, authentifié, sans limite de débit)
curl -X POST http://localhost:8000/diagnostic/comparer \
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

Aucune commande à lancer séparément : le bouton **« 🖊️ Pré-remplir la souscription »** (fiche prospect, fiche client/contrat — uniquement pour les opérateurs **Free** et **Bouygues**) ouvre directement, depuis l'app, un navigateur Chromium **visible** et pré-rempli avec les coordonnées du client. Le conseiller vérifie et valide lui-même sur le site — **rien n'est jamais soumis automatiquement**.

Prérequis : `playwright install chromium` (voir §2) doit avoir été exécuté au moins une fois sur le poste.

---

## 9. Tests automatisés

### 9.1 Lancer la suite localement
```bash
cd src
pytest -q
```
Couvre : auth, moteur d'offres, utils, pdf_engine, prospects_engine, souscription_engine (fixtures communes dans `tests/conftest.py`).

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

---

## 10. Récapitulatif — tout lancer en une fois (usage quotidien complet)

Ouvrir 3 terminaux séparés (chacun dans `src/`, environnement virtuel activé) :

```bash
# Terminal 1 — l'application principale (obligatoire)
streamlit run app.py

# Terminal 2 — API CRM interne (optionnelle : Streamlit fonctionne sans, avec repli automatique)
uvicorn crm_api:app --host 0.0.0.0 --port 8000

# Terminal 3 — API chatbot publique (optionnelle : uniquement si le widget de site est utilisé)
uvicorn chatbot_api:app --host 0.0.0.0 --port 8001
```

Et en tâches planifiées (pas de terminal à garder ouvert) :
```bash
python notifications.py        # tous les matins, ex. 08:00
python veille_prix_engine.py   # tous les matins, ex. 07:00
```

### Ports par défaut
| Service | Port | Authentifié ? |
|---|---|---|
| Streamlit (`app.py`) | 8501 | Session login (formulaire) |
| API CRM interne (`crm_api.py`) | 8000 | Oui — JWT |
| API chatbot publique (`chatbot_api.py`) | 8001 | Non (rate-limit 30 req/min/IP) |

---

## 11. Dépannage rapide

| Symptôme | Cause probable | Solution |
|---|---|---|
| `⚠️ API CRM interne injoignable` dans Streamlit | `crm_api.py` non lancé | Sans gravité — Streamlit fonctionne en accès direct base. Lancer l'API (§4) si besoin. |
| OCR Vision inactif / factures lues par regex uniquement | Clé API Anthropic absente | Configurer dans **Admin > 🔍 OCR Vision** |
| Bouton pré-remplissage souscription sans effet | Chromium Playwright non installé | `playwright install chromium` |
| Veille prix : « package playwright non installé » | idem | `pip install playwright && playwright install chromium` |
| Emails non envoyés (teaser, alertes, digest) | SMTP non configuré | Renseigner **Admin > 📧 Email** |
| `notifications.py`/`veille_prix_engine.py` : rien ne se passe | Pas de relance/changement de prix ce jour-là | Comportement normal — le script journalise silencieusement s'il n'y a rien à signaler |
| JWT expiré côté API | Jeton valide 8h | Se reconnecter (`POST /auth/login`) ou redémarrer la session Streamlit |

---

Pour la description fonctionnelle complète de l'application (pages, workflows métier, schéma de base de données, sécurité), voir **`IA.CONSEIL.MD`**. Pour la feuille de route et les prochaines évolutions, voir **`IA_CONSEIL_ROADMAP.md`**.
