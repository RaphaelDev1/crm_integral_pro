#!/usr/bin/env bash
# Lance l'application complète (Redis, backend, Celery worker+beat+Flower,
# conseiller, portail) sous Linux (Chromebook / Crostini). Équivalent bash de
# lancer-app.ps1 (Windows). Pré-requis (.env remplis, migrations appliquées,
# npm install fait) : voir LANCEMENT_LINUX.md §0-4.
#
# Usage : ./lancer-app.sh
#         ./lancer-app.sh --sans-celery   # saute worker/beat/Flower (dev rapide
#                                          # conseiller/portail, sans tâches de fond)
#
# Contrairement à la version Windows (une fenêtre PowerShell par service), tout
# tourne ici en arrière-plan dans CE terminal : les logs de chaque service sont
# écrits dans logs/*.log (voir "tail -f" suggéré à la fin). Ctrl+C dans ce
# terminal arrête proprement tous les services (et le conteneur Redis).

set -u

SANS_CELERY=0
for arg in "$@"; do
  case "$arg" in
    --sans-celery) SANS_CELERY=1 ;;
    *) echo "Argument inconnu : $arg (usage : ./lancer-app.sh [--sans-celery])" >&2; exit 1 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo -e "\033[90mDémarrage depuis : $ROOT\033[0m"

mkdir -p logs
PIDS=()
REDIS_CONTAINER="cmr-redis-dev"
REDIS_LANCE=0

cleanup() {
  echo ""
  echo -e "\033[90mArrêt des services...\033[0m"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null
  done
  if [ "$REDIS_LANCE" = "1" ]; then
    docker stop "$REDIS_CONTAINER" >/dev/null 2>&1
  fi
  wait 2>/dev/null
  echo -e "\033[90mTerminé.\033[0m"
}
trap cleanup INT TERM

if [ ! -x ".venv/bin/python" ]; then
  echo -e "\033[31m✗ .venv/bin/python introuvable — crée le venv d'abord (voir LANCEMENT_LINUX.md §2) : python3.11 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements-dev.txt\033[0m" >&2
  exit 1
fi

if command -v docker >/dev/null 2>&1; then
  docker run -d --rm --name "$REDIS_CONTAINER" -p 6379:6379 redis:7-alpine >/dev/null 2>&1 \
    && REDIS_LANCE=1 \
    || echo -e "\033[33m⚠ Impossible de démarrer le conteneur Redis (peut-être déjà lancé sous le nom '$REDIS_CONTAINER') : Celery risque d'échouer.\033[0m"
else
  echo -e "\033[33m⚠ Docker introuvable dans le PATH : Redis non lancé (nécessaire pour Celery/KYC async ; sans lui, la trame IA Conseil du diagnostic fonctionne aussi mais sans les mises à jour temps réel entre onglets).\033[0m"
fi

echo -e "\033[90mApplication des migrations (alembic upgrade head)...\033[0m"
if ! .venv/bin/python -m alembic -c "$ROOT/alembic.ini" upgrade head; then
  echo -e "\033[31m⚠ Échec des migrations alembic — le backend risque de renvoyer des 500 (schéma BDD désynchronisé du code). Corrige l'erreur ci-dessus avant de continuer.\033[0m"
fi

.venv/bin/python -m uvicorn backend.main:app --reload --port 8000 > logs/backend.log 2>&1 &
PIDS+=($!)

if [ "$SANS_CELERY" = "1" ]; then
  echo -e "\033[33m⚠ --sans-celery : worker/beat/Flower non lancés — les tâches de fond (relance dossiers, LRE, veille prix, catalogue, digest quotidien, email J+1 landing) ne tourneront pas.\033[0m"
elif [ "$REDIS_LANCE" != "1" ]; then
  echo -e "\033[33m⚠ Celery worker/beat/Flower non lancés (pas de Redis démarré) — installe/démarre Docker, ou lance Redis manuellement, puis relance sans --sans-celery.\033[0m"
else
  .venv/bin/python -m celery -A backend.workers.celery_app worker --loglevel=info > logs/celery-worker.log 2>&1 &
  PIDS+=($!)

  .venv/bin/python -m celery -A backend.workers.celery_app beat --loglevel=info > logs/celery-beat.log 2>&1 &
  PIDS+=($!)

  .venv/bin/python -m celery -A backend.workers.celery_app flower --port=5555 > logs/celery-flower.log 2>&1 &
  PIDS+=($!)
fi

(cd "$ROOT/frontend-conseiller" && npm run dev > "$ROOT/logs/frontend-conseiller.log" 2>&1) &
PIDS+=($!)

(cd "$ROOT/frontend-portail" && npm run dev > "$ROOT/logs/frontend-portail.log" 2>&1) &
PIDS+=($!)

echo -e "\033[32mServices lancés (logs dans logs/, Ctrl+C ici pour tout arrêter) :\033[0m"
[ "$REDIS_LANCE" = "1" ] && echo "  - Redis            -> localhost:6379 (broker/backend Celery + rate limiting landing)"
echo "  - Backend FastAPI  -> http://localhost:8000/docs           (logs/backend.log)"
if [ "$SANS_CELERY" != "1" ] && [ "$REDIS_LANCE" = "1" ]; then
  echo "  - Celery worker    -> file 'ia_conseil' (KYC, Yousign, LRE, veille, catalogue, email J+1 landing...) (logs/celery-worker.log)"
  echo "  - Celery beat      -> planifie les tâches périodiques (voir backend/workers/celery_app.py::beat_schedule) (logs/celery-beat.log)"
  echo "  - Flower           -> http://localhost:5555 (monitoring des tâches Celery) (logs/celery-flower.log)"
fi
echo "  - Conseiller       -> http://localhost:3001  (dont Dashboard UTM -> /dashboard/utm) (logs/frontend-conseiller.log)"
echo "  - IA Conseil       -> http://localhost:3001/ia-conseil/clients  (trame adaptative live)"
echo "  - Portail client   -> http://localhost:3000  (landing lead : /economiser) (logs/frontend-portail.log)"
echo ""
echo -e "\033[90mSuivre un service en direct : tail -f logs/<service>.log\033[0m"
echo -e "\033[90mSur Chromebook, ouvrir les URLs ci-dessus dans Chrome — Crostini redirige automatiquement les ports du conteneur Linux vers localhost côté ChromeOS.\033[0m"
echo ""
echo -e "\033[90mRappel : la landing /economiser fonctionne sans clé API externe configurée (dégradation propre)\033[0m"
echo -e "\033[90mRappel : IA Conseil nécessite un catalogue seedé une première fois : python -m backend.scripts.seed_ia_conseil (idempotent).\033[0m"
echo ""
echo "Appuie sur Ctrl+C pour arrêter tous les services."

wait
