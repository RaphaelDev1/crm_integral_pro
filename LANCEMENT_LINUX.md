# Lancer le projet sous Linux (Chromebook / Crostini)

> Adaptation Linux/bash de `GUIDE_LANCEMENT.md` et `frontend-conseiller/LANCEMENT.md` (écrits en
> PowerShell pour Windows). Périmètre couvert ici : backend FastAPI + `frontend-conseiller`
> (l'outil interne conseiller en Next.js), suffisant pour travailler au quotidien depuis un
> Chromebook avec le conteneur Linux (Crostini) activé.

---

## 0. Pré-requis (une seule fois sur le Chromebook)

Dans le terminal Linux (Crostini) :

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git

# Node.js 20 (via nvm, plus simple à maintenir que le paquet apt)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20
```

Vérifier :

```bash
python3.11 --version   # Python 3.11.x
node --version         # v20.x
```

Docker est optionnel (utile pour Redis/Postgres local) — sur Chromebook, `docker.io` fonctionne
dans Crostini :

```bash
sudo apt install -y docker.io
sudo usermod -aG docker $USER   # puis se déconnecter/reconnecter du terminal Linux
```

## 1. Récupérer le projet

```bash
git clone https://github.com/RaphaelDev1/crm_integral_pro.git cmr_integral_pro
cd cmr_integral_pro
```

Si le dossier existe déjà (mise à jour d'une session précédente) :

```bash
cd cmr_integral_pro
git pull
```

## 2. Configurer le backend

```bash
python3.11 -m venv .venv
source .venv/bin/activate

pip install -r backend/requirements-dev.txt

cp backend/.env.example backend/.env
# Éditer backend/.env (nano, vim, ou l'éditeur de fichiers du Chromebook via le dossier "Linux") :
#   - DATABASE_URL   (Neon Postgres, ou Postgres local si docker compose --profile local-db)
#   - CRM_API_SECRET (générer avec : python -c "import secrets; print(secrets.token_urlsafe(48))")
#   - ANTHROPIC_API_KEY (si besoin de l'agent d'audit / diagnostic)
```

## 3. Migrations Alembic (obligatoire avant tout)

```bash
python -m alembic upgrade head
python -m alembic current   # doit afficher "0020 (head)" (ou plus récent)
```

## 4. Créer le premier compte admin (une seule fois, table utilisateurs vide)

```bash
python -m backend.scripts.seed_admin
# Note l'identifiant "admin" et le mot de passe généré, affiché une seule fois.
```

## 5. Lancer le backend

Dans un premier terminal (venv activé) :

```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Vérification : `http://localhost:8000/health` → `200 OK`, `http://localhost:8000/docs` → Swagger.

> Redis/Celery ne sont nécessaires que pour la validation KYC async et l'envoi Yousign — pas requis
> pour se connecter et naviguer dans frontend-conseiller. Si besoin :
> ```bash
> docker run -p 6379:6379 redis:7-alpine
> celery -A backend.workers.celery_app worker --loglevel=info --pool=solo
> ```

## 6. Configurer et lancer frontend-conseiller

Dans un second terminal :

```bash
cd cmr_integral_pro/frontend-conseiller
cp .env.example .env.local
# .env.local doit contenir :
#   BACKEND_URL=http://localhost:8000
#   NEXT_PUBLIC_SENTRY_DSN=

npm install
npm run dev
```

Démarre sur **`http://localhost:3001`**.

> Sur Chromebook, ouvrir `http://localhost:3001` dans le navigateur Chrome habituel — Crostini
> redirige automatiquement les ports du conteneur Linux vers `localhost` côté ChromeOS, pas de
> configuration réseau supplémentaire nécessaire.

## 7. Se connecter

1. `http://localhost:3001` → redirection vers `/login`.
2. Identifiant/mot de passe `admin` généré à l'étape 4.
3. Changement de mot de passe exigé à la première connexion.
4. Redirection vers `/dashboard`.

## 8. Tests / lint (optionnel)

```bash
# Backend
source .venv/bin/activate
python -m pytest backend/tests -q
ruff check backend

# frontend-conseiller
cd frontend-conseiller
npm run lint
npm test
npm run test:e2e   # nécessite le backend déjà lancé (étape 5)
```

## 9. Problèmes fréquents

| Symptôme | Cause | Solution |
|---|---|---|
| `command not found: python3.11` | Paquet non installé | `sudo apt install python3.11 python3.11-venv` |
| Boucle infinie vers `/login` | Backend arrêté ou `DATABASE_URL` invalide | Vérifier `http://localhost:8000/health` |
| Connexion échoue avec identifiant/mot de passe corrects | Pas de compte encore créé | Relancer `python -m backend.scripts.seed_admin` |
| Port déjà utilisé (`EADDRINUSE`) | Une instance précédente tourne encore | `lsof -i :8000` / `lsof -i :3001` puis `kill <PID>` |
| npm install très lent ou échoue | Version Node incorrecte | Vérifier `node --version` → doit être v20.x (`nvm use 20`) |

## 10. Reprendre le travail le lendemain

```bash
cd cmr_integral_pro
git pull

# Terminal 1
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Terminal 2
cd frontend-conseiller
npm run dev
```
