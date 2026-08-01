# ==============================================================================
#  VEILLE PRIX — CRUD des sources surveillées + consultation historique/alertes
#  et validation/rejet manuel. Le relevé automatique est déclenché par la
#  tâche Celery Beat périodique (backend/workers/tasks.py::lancer_veille_periodique) ;
#  `/veille/lancer` permet un déclenchement manuel immédiat depuis l'admin.
#  Réservé au rôle Admin : la veille pilote le catalogue commercial.
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import require_role
from backend.models.veille import SourceVeille, VeilleAlerte, VeilleHistoriquePrix
from backend.schemas.veille import (
    SourceVeilleCreate,
    SourceVeilleOut,
    SourceVeilleUpdate,
    VeilleAlerteOut,
    VeilleHistoriquePrixOut,
)
from backend.services import veille_engine

router = APIRouter(prefix="/veille", tags=["veille"], dependencies=[Depends(require_role("Admin"))])


@router.get("/sources", response_model=list[SourceVeilleOut])
async def lister_sources(actif_seulement: bool = False, db: AsyncSession = Depends(get_db)):
    requete = select(SourceVeille).order_by(SourceVeille.fournisseur, SourceVeille.nom_offre)
    if actif_seulement:
        requete = requete.where(SourceVeille.actif.is_(True))
    result = await db.execute(requete)
    return result.scalars().all()


@router.post("/sources", response_model=SourceVeilleOut, status_code=status.HTTP_201_CREATED)
async def creer_source(payload: SourceVeilleCreate, db: AsyncSession = Depends(get_db)):
    source = SourceVeille(**payload.model_dump(), date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"))
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.put("/sources/{source_id}", response_model=SourceVeilleOut)
async def maj_source(source_id: int, payload: SourceVeilleUpdate, db: AsyncSession = Depends(get_db)):
    source = await db.get(SourceVeille, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source introuvable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(source, champ, valeur)
    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_source(source_id: int, db: AsyncSession = Depends(get_db)):
    source = await db.get(SourceVeille, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source introuvable.")
    await db.delete(source)
    await db.commit()


@router.get("/sources/{source_id}/historique", response_model=list[VeilleHistoriquePrixOut])
async def historique_prix(source_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(VeilleHistoriquePrix).where(VeilleHistoriquePrix.source_id == source_id).order_by(VeilleHistoriquePrix.id)
    )
    return result.scalars().all()


@router.get("/alertes", response_model=list[VeilleAlerteOut])
async def lister_alertes(statut: str = "en_attente", db: AsyncSession = Depends(get_db)):
    requete = select(VeilleAlerte).order_by(VeilleAlerte.id.desc())
    if statut:
        requete = requete.where(VeilleAlerte.statut == statut)
    result = await db.execute(requete)
    return result.scalars().all()


@router.post("/alertes/{alerte_id}/valider", response_model=dict)
async def valider_alerte(alerte_id: int, db: AsyncSession = Depends(get_db)):
    ok, message = await veille_engine.valider_alerte(db, alerte_id)
    if not ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)
    return {"ok": True, "message": message}


@router.post("/alertes/{alerte_id}/rejeter", response_model=dict)
async def rejeter_alerte(alerte_id: int, db: AsyncSession = Depends(get_db)):
    ok = await veille_engine.rejeter_alerte(db, alerte_id)
    if not ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Alerte introuvable ou déjà traitée.")
    return {"ok": True}


@router.post("/lancer", response_model=list[dict])
async def lancer_veille_manuelle(db: AsyncSession = Depends(get_db)):
    """Déclenchement manuel immédiat (hors planification Celery Beat) — utile
    pour tester une source fraîchement ajoutée sans attendre le prochain
    passage quotidien."""
    alertes = await veille_engine.lancer_veille(db)
    if alertes:
        from backend.services import notification_engine
        await notification_engine.notifier_changement_prix(db, alertes)
    return alertes
