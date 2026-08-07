# ==============================================================================
#  STOCKAGE LOCAL — sert les fichiers du repli disque local de secours (voir
#  backend/services/storage_engine.py::_stockage_local_actif, dev uniquement,
#  jamais utilisé en production où S3 reste obligatoire).
#
#  Pas d'authentification : ce mode n'est actif que quand S3_BUCKET n'est pas
#  configuré, donc sur la machine de dev d'un conseiller — jamais en
#  production (_stockage_local_actif lève une erreur si APP_ENV=production).
# ==============================================================================
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from backend.services.storage_engine import resoudre_fichier_local

router = APIRouter(prefix="/stockage-local", tags=["stockage_local"])


@router.get("/{cle:path}")
async def obtenir_fichier_local(cle: str):
    chemin = resoudre_fichier_local(cle)
    if chemin is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable.")
    return FileResponse(chemin)
