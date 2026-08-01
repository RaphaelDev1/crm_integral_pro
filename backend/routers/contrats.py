# ==============================================================================
#  CONTRATS — CRUD, protégé par JWT. Rattachés à un client (fiche client,
#  onglet Contrats). Chaque écriture est journalisée sur l'entité "client"
#  (backend/services/audit_engine.py) pour apparaître dans son historique.
# ==============================================================================
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.contrat import Contrat
from backend.models.user import User
from backend.schemas.contrat import ContratCreate, ContratOut, ContratUpdate
from backend.services import audit_engine

router = APIRouter(prefix="/contrats", tags=["contrats"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ContratOut])
async def lister_contrats(client_id: int | None = None, db: AsyncSession = Depends(get_db)):
    requete = select(Contrat).order_by(Contrat.id.desc())
    if client_id is not None:
        requete = requete.where(Contrat.client_id == client_id)
    result = await db.execute(requete)
    return result.scalars().all()


@router.get("/{contrat_id}", response_model=ContratOut)
async def obtenir_contrat(contrat_id: int, db: AsyncSession = Depends(get_db)):
    contrat = await db.get(Contrat, contrat_id)
    if contrat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrat introuvable.")
    return contrat


@router.post("", response_model=ContratOut, status_code=status.HTTP_201_CREATED)
async def creer_contrat(
    payload: ContratCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contrat = Contrat(**payload.model_dump(), cree_par=user.nom_complet)
    db.add(contrat)
    await audit_engine.enregistrer_action(
        db, entite_type="client", entite_id=payload.client_id,
        action="Contrat ajouté", details=payload.fournisseur, auteur=user.nom_complet,
    )
    await db.commit()
    await db.refresh(contrat)
    return contrat


@router.put("/{contrat_id}", response_model=ContratOut)
async def maj_contrat(
    contrat_id: int,
    payload: ContratUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contrat = await db.get(Contrat, contrat_id)
    if contrat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrat introuvable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(contrat, champ, valeur)
    if contrat.client_id is not None:
        await audit_engine.enregistrer_action(
            db, entite_type="client", entite_id=contrat.client_id,
            action="Contrat modifié", details=contrat.fournisseur, auteur=user.nom_complet,
        )
    await db.commit()
    await db.refresh(contrat)
    return contrat


@router.delete("/{contrat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_contrat(
    contrat_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contrat = await db.get(Contrat, contrat_id)
    if contrat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrat introuvable.")
    if contrat.client_id is not None:
        await audit_engine.enregistrer_action(
            db, entite_type="client", entite_id=contrat.client_id,
            action="Contrat supprimé", details=contrat.fournisseur, auteur=user.nom_complet,
        )
    await db.delete(contrat)
    await db.commit()
