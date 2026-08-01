# ==============================================================================
#  COMPARAISONS D'OFFRES — enregistrements historiques (pas de PUT/DELETE),
#  protégé par JWT. La logique de calcul (comparer_offres/construire_recommandations)
#  vit dans backend/services/offres_engine.py — ce router ne fait que persister le résultat.
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.comparaison_offre import ComparaisonOffre
from backend.models.user import User
from backend.schemas.comparaison_offre import ComparaisonOffreCreate, ComparaisonOffreOut

router = APIRouter(prefix="/comparaisons-offres", tags=["comparaisons-offres"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ComparaisonOffreOut])
async def lister_comparaisons(
    prospect_id: int | None = None,
    client_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    requete = select(ComparaisonOffre).order_by(ComparaisonOffre.id.desc())
    if prospect_id is not None:
        requete = requete.where(ComparaisonOffre.prospect_id == prospect_id)
    if client_id is not None:
        requete = requete.where(ComparaisonOffre.client_id == client_id)
    result = await db.execute(requete)
    return result.scalars().all()


@router.get("/{comparaison_id}", response_model=ComparaisonOffreOut)
async def obtenir_comparaison(comparaison_id: int, db: AsyncSession = Depends(get_db)):
    comparaison = await db.get(ComparaisonOffre, comparaison_id)
    if comparaison is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comparaison introuvable.")
    return comparaison


@router.post("", response_model=ComparaisonOffreOut, status_code=status.HTTP_201_CREATED)
async def creer_comparaison(
    payload: ComparaisonOffreCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if (payload.prospect_id is None) == (payload.client_id is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Renseigner exactement un des deux champs prospect_id ou client_id.",
        )
    donnees = payload.model_dump()
    donnees["offres_comparees"] = [o for o in (donnees.get("offres_comparees") or [])]
    comparaison = ComparaisonOffre(
        **donnees,
        date_comparaison=datetime.now().strftime("%d/%m/%Y %H:%M"),
        cree_par=user.nom_complet,
    )
    db.add(comparaison)
    await db.commit()
    await db.refresh(comparaison)
    return comparaison
