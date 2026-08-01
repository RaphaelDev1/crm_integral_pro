# ==============================================================================
#  ALERTES OFFRES — consultation et validation/rejet des alertes détectées
#  par la tâche Celery Beat périodique
#  (backend/workers/tasks.py::detecter_offres_moins_cheres_periodique).
#  Accessible à tout conseiller connecté (pas restreint à Admin comme
#  /veille) : ces alertes concernent directement les clients qu'il suit.
# ==============================================================================
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.alerte_offre import AlerteOffre
from backend.schemas.alerte_offre import AlerteOffreOut
from backend.services import alertes_offres_engine

router = APIRouter(prefix="/alertes-offres", tags=["alertes_offres"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[AlerteOffreOut])
async def lister_alertes(
    statut: str = "en_attente",
    client_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    requete = select(AlerteOffre).order_by(AlerteOffre.id.desc())
    if statut:
        requete = requete.where(AlerteOffre.statut == statut)
    if client_id is not None:
        requete = requete.where(AlerteOffre.client_id == client_id)
    result = await db.execute(requete)
    return result.scalars().all()


@router.post("/{alerte_id}/valider", response_model=dict)
async def valider_alerte(alerte_id: int, db: AsyncSession = Depends(get_db)):
    ok, message = await alertes_offres_engine.valider_alerte(db, alerte_id)
    if not ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)
    return {"ok": True, "message": message}


@router.post("/{alerte_id}/rejeter", response_model=dict)
async def rejeter_alerte(alerte_id: int, db: AsyncSession = Depends(get_db)):
    ok = await alertes_offres_engine.rejeter_alerte(db, alerte_id)
    if not ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Alerte introuvable ou déjà traitée.")
    return {"ok": True}
