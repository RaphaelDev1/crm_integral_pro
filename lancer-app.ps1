# Lance l'application complète (Redis, backend, Celery worker+beat, Flower,
# conseiller, portail) dans des fenêtres PowerShell séparées. Pré-requis (.env
# remplis, migrations appliquées, npm install fait) : voir GUIDE_LANCEMENT.md §0-1.
#
# Usage : .\lancer-app.ps1
#         .\lancer-app.ps1 -SansCelery   # saute worker/beat/Flower (dev rapide
#                                          # conseiller/portail, sans tâches de fond)

param(
    [switch]$SansCelery
)

$root = if ($PSScriptRoot) { $PSScriptRoot } else { $PWD.Path }

Write-Host "Démarrage depuis : $root" -ForegroundColor DarkGray

$redisLance = $false
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", `
      "docker run --rm -p 6379:6379 redis:7-alpine"
    $redisLance = $true
} else {
    Write-Host "⚠ Docker introuvable dans le PATH : Redis non lancé (nécessaire pour Celery/KYC async ; sans lui, la trame IA Conseil du diagnostic fonctionne aussi mais sans les mises à jour temps réel entre onglets)." -ForegroundColor Yellow
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", `
  "cd '$root'; .venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000"

if ($SansCelery) {
    Write-Host "⚠ -SansCelery : worker/beat/Flower non lancés — les tâches de fond (relance dossiers, LRE, veille prix, catalogue, digest quotidien, email J+1 landing) ne tourneront pas." -ForegroundColor Yellow
} elseif (-not $redisLance) {
    Write-Host "⚠ Celery worker/beat/Flower non lancés (pas de Redis démarré) — installe Docker ou démarre Redis manuellement, puis relance sans -SansCelery." -ForegroundColor Yellow
} else {
    # --pool=solo : le pool prefork par défaut de Celery ne fonctionne pas sur
    # Windows (pas de fork()) — voir GUIDE_LANCEMENT.md §2.
    Start-Process powershell -ArgumentList "-NoExit", "-Command", `
      "cd '$root'; .venv\Scripts\python.exe -m celery -A backend.workers.celery_app worker --loglevel=info --pool=solo"

    Start-Process powershell -ArgumentList "-NoExit", "-Command", `
      "cd '$root'; .venv\Scripts\python.exe -m celery -A backend.workers.celery_app beat --loglevel=info"

    Start-Process powershell -ArgumentList "-NoExit", "-Command", `
      "cd '$root'; .venv\Scripts\python.exe -m celery -A backend.workers.celery_app flower --port=5555"
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", `
  "cd '$root\frontend-conseiller'; npm run dev"

Start-Process powershell -ArgumentList "-NoExit", "-Command", `
  "cd '$root\frontend-portail'; npm run dev"

Write-Host "Fenêtres lancées :" -ForegroundColor Green
Write-Host "  - Redis            -> localhost:6379 (broker/backend Celery + rate limiting landing)"
Write-Host "  - Backend FastAPI  -> http://localhost:8000/docs"
if (-not $SansCelery -and $redisLance) {
    Write-Host "  - Celery worker    -> file 'ia_conseil' (KYC, Yousign, LRE, veille, catalogue, email J+1 landing...)"
    Write-Host "  - Celery beat      -> planifie les tâches périodiques (voir backend/workers/celery_app.py::beat_schedule)"
    Write-Host "  - Flower           -> http://localhost:5555 (monitoring des tâches Celery)"
}
Write-Host "  - Conseiller       -> http://localhost:3001  (dont Dashboard UTM -> /dashboard/utm)"
Write-Host "  - IA Conseil       -> http://localhost:3001/ia-conseil/clients  (trame adaptative live)"
Write-Host "  - Portail client   -> http://localhost:3000  (landing lead : /economiser)"
Write-Host "Fermer chaque fenêtre (ou Ctrl+C dedans) pour arrêter le service correspondant."
Write-Host ""
Write-Host "Rappel : la landing /economiser (capture de leads, autocomplétion adresse, détection FAI," -ForegroundColor DarkGray
Write-Host "captcha Turnstile, éligibilité fibre) fonctionne sans clé API externe configurée (dégradation" -ForegroundColor DarkGray
Write-Host "propre) mais nécessite les migrations 0027-0029 appliquées (leads_capture, leads_enrichissements," -ForegroundColor DarkGray
Write-Host "utm_dashboard_attribution) — voir GUIDE_LANCEMENT.md §1." -ForegroundColor DarkGray
Write-Host ""
Write-Host "Rappel : IA Conseil (trame adaptative mobile/box/énergie) nécessite les migrations 0032-0036" -ForegroundColor DarkGray
Write-Host "appliquées (python -m alembic upgrade head) et un catalogue seedé une première fois :" -ForegroundColor DarkGray
Write-Host "python -m backend.scripts.seed_ia_conseil (idempotent, à relancer sans risque)." -ForegroundColor DarkGray
