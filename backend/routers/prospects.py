# ==============================================================================
#  PROSPECTS — CRUD, protégé par JWT (get_current_user).
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.prospect import Prospect
from backend.models.user import User
from backend.schemas.prospect import ProspectCreate, ProspectOut, ProspectUpdate

router = APIRouter(prefix="/prospects", tags=["prospects"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ProspectOut])
async def lister_prospects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prospect).order_by(Prospect.id.desc()))
    return result.scalars().all()


@router.get("/{prospect_id}", response_model=ProspectOut)
async def obtenir_prospect(prospect_id: int, db: AsyncSession = Depends(get_db)):
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    return prospect


@router.post("", response_model=ProspectOut, status_code=status.HTTP_201_CREATED)
async def creer_prospect(
    payload: ProspectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    prospect = Prospect(
        **payload.model_dump(),
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
        cree_par=user.nom_complet,
    )
    db.add(prospect)
    await db.commit()
    await db.refresh(prospect)
    return prospect


@router.put("/{prospect_id}", response_model=ProspectOut)
async def maj_prospect(prospect_id: int, payload: ProspectUpdate, db: AsyncSession = Depends(get_db)):
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(prospect, champ, valeur)
    await db.commit()
    await db.refresh(prospect)
    return prospect


@router.delete("/{prospect_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_prospect(prospect_id: int, db: AsyncSession = Depends(get_db)):
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    await db.delete(prospect)
    await db.commit()
