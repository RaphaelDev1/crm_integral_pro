# ==============================================================================
#  Image backend FastAPI (+ workers Celery, même image, commande différente en
#  docker-compose.yml). Contexte de build = racine du dépôt (le package
#  `backend` importe `backend.core...`, il lui faut donc `backend/` comme
#  sous-dossier d'un répertoire de travail qui est sur le PYTHONPATH).
#  Build : docker build -f backend/Dockerfile -t ia-conseil-backend .
# ==============================================================================
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY alembic.ini alembic.ini

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
