# ==============================================================================
#  OFFRES — comparaison et recommandations (moteur de calcul dans
#  backend/services/offres_engine.py). Protégé par JWT ; le catalogue
#  (CRUD `offres`) reste géré côté Streamlit pour l'instant.
# ==============================================================================
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.schemas.offre import (
    BlocRecommandationOut,
    ComparerOffresRequest,
    OffreCompareeOut,
    RecommandationsOut,
    RecommandationsRequest,
)
from backend.services import offres_engine

router = APIRouter(prefix="/offres", tags=["offres"], dependencies=[Depends(get_current_user)])


@router.post("/comparer", response_model=list[OffreCompareeOut])
async def comparer(payload: ComparerOffresRequest, db: AsyncSession = Depends(get_db)):
    return await offres_engine.comparer_offres(
        db,
        payload.univers,
        payload.categorie,
        payload.cout_actuel_mensuel,
        fournisseurs_autorises=payload.fournisseurs_autorises,
        fournisseur_exclu=payload.fournisseur_exclu,
        data_go_min=payload.data_go_min,
    )


@router.post("/recommandations", response_model=RecommandationsOut)
async def recommandations(payload: RecommandationsRequest, db: AsyncSession = Depends(get_db)):
    resultat = await offres_engine.construire_recommandations(
        db,
        payload.service_principal,
        payload.cout_tel,
        fournisseurs_autorises=payload.fournisseurs_autorises,
        fournisseur_exclu=payload.fournisseur_exclu,
        data_go_min=payload.data_go_min,
    )
    titre_principal, categorie_principal, offres_principal = resultat["principal"]
    return RecommandationsOut(
        principal=BlocRecommandationOut(titre=titre_principal, categorie=categorie_principal, offres=offres_principal),
        cross_sell=[
            BlocRecommandationOut(titre=titre, categorie=categorie, offres=offres)
            for titre, categorie, offres in resultat["cross_sell"]
        ],
    )
