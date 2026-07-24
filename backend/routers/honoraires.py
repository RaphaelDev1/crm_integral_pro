# ==============================================================================
#  HONORAIRES — mandat de rémunération du cabinet, rattaché à un dossier.
#  Distinct de `routers/factures.py` (analyse LLM des factures opérateur du
#  client) et de `mandats` (signature Yousign du mandat de représentation).
#  Protégé par JWT (conseillers uniquement).
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.dossier import Dossier
from backend.models.mandat_honoraires import MandatHonoraires
from backend.schemas.mandat_honoraires import (
    MandatHonorairesCreate,
    MandatHonorairesOut,
    MarquerSigneHonoraires,
)

router = APIRouter(prefix="/dossiers", tags=["honoraires"], dependencies=[Depends(get_current_user)])


@router.get("/{dossier_id}/mandat-honoraires", response_model=MandatHonorairesOut | None)
async def obtenir_mandat_honoraires(dossier_id: int, db: AsyncSession = Depends(get_db)):
    return (
        await db.execute(select(MandatHonoraires).where(MandatHonoraires.dossier_id == dossier_id))
    ).scalar_one_or_none()


@router.post("/{dossier_id}/mandat-honoraires", response_model=MandatHonorairesOut, status_code=status.HTTP_201_CREATED)
async def creer_mandat_honoraires(
    dossier_id: int, payload: MandatHonorairesCreate, db: AsyncSession = Depends(get_db)
):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    existant = (
        await db.execute(select(MandatHonoraires).where(MandatHonoraires.dossier_id == dossier_id))
    ).scalar_one_or_none()
    if existant is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Un mandat d'honoraires existe déjà pour ce dossier.")
    mandat = MandatHonoraires(
        dossier_id=dossier_id,
        montant=payload.montant,
        taux=payload.taux,
        statut="envoye",
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )
    db.add(mandat)
    await db.commit()
    await db.refresh(mandat)
    return mandat


@router.post("/{dossier_id}/mandat-honoraires/marquer-signe", response_model=MandatHonorairesOut)
async def marquer_signe_honoraires(
    dossier_id: int, payload: MarquerSigneHonoraires, db: AsyncSession = Depends(get_db)
):
    mandat = (
        await db.execute(select(MandatHonoraires).where(MandatHonoraires.dossier_id == dossier_id))
    ).scalar_one_or_none()
    if mandat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun mandat d'honoraires pour ce dossier.")
    mandat.statut = "signe"
    mandat.signataire = payload.signataire
    mandat.date_signature = datetime.now().strftime("%d/%m/%Y %H:%M")
    await db.commit()
    await db.refresh(mandat)
    return mandat
