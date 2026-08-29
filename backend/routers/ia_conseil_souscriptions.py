# ==============================================================================
#  SOUSCRIPTIONS (IA Conseil) — enregistrement d'une souscription à l'issue
#  d'une trame + suivi des commissions. PLAN_IMPLEMENTATION_4_PHASES.md §0.5.
#
#  Calcul commission_prevue : taux_commission (%, sur le fournisseur de
#  l'offre) appliqué au prix mensuel négocié — une estimation mensuelle
#  simple, le plan ne précisant pas de formule plus détaillée à ce stade.
# ==============================================================================
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.ia_conseil import Fournisseur, OffreConseil, Souscription
from backend.models.user import User
from backend.schemas.ia_conseil import SouscriptionCreate, SouscriptionOut
from backend.services import alertes_engine

router = APIRouter(prefix="/api/v1/souscriptions", tags=["ia_conseil_souscriptions"], dependencies=[Depends(get_current_user)])


async def _calculer_commission_prevue(db: AsyncSession, offre_id: uuid.UUID, prix_mensuel_negocie: float | None) -> float | None:
    if prix_mensuel_negocie is None:
        return None
    offre = await db.get(OffreConseil, offre_id)
    if offre is None or offre.fournisseur_id is None:
        return None
    fournisseur = await db.get(Fournisseur, offre.fournisseur_id)
    if fournisseur is None or fournisseur.taux_commission is None:
        return None
    return round(float(prix_mensuel_negocie) * float(fournisseur.taux_commission) / 100, 2)


@router.get("", response_model=list[SouscriptionOut])
async def lister_souscriptions(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(Souscription).order_by(Souscription.date_souscription.desc().nulls_last())
    if user.role != "Admin":
        query = query.where(Souscription.conseiller_id == user.id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/commissions")
async def commissions(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(
        Souscription.conseiller_id,
        func.coalesce(func.sum(Souscription.commission_prevue), 0).label("total_prevue"),
        func.coalesce(func.sum(Souscription.commission_encaissee), 0).label("total_encaissee"),
        func.count(Souscription.id).label("nb_souscriptions"),
    ).group_by(Souscription.conseiller_id)
    if user.role != "Admin":
        query = query.where(Souscription.conseiller_id == user.id)
    result = await db.execute(query)
    return [
        {
            "conseiller_id": ligne.conseiller_id,
            "commission_prevue_totale": float(ligne.total_prevue),
            "commission_encaissee_totale": float(ligne.total_encaissee),
            "nb_souscriptions": ligne.nb_souscriptions,
        }
        for ligne in result.all()
    ]


@router.post("", response_model=SouscriptionOut, status_code=status.HTTP_201_CREATED)
async def creer_souscription(
    payload: SouscriptionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offre = await db.get(OffreConseil, payload.offre_id)
    if offre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offre introuvable.")

    if payload.session_id is not None:
        alertes_bloquantes = await alertes_engine.alertes_critiques_non_levees(db, payload.session_id, payload.offre_id)
        if alertes_bloquantes:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={
                    "message": "Alerte(s) critique(s) non levée(s) sur cette offre — lever via /sessions/{id}/override-alerte avant de souscrire.",
                    "alertes": alertes_bloquantes,
                },
            )

    commission_prevue = await _calculer_commission_prevue(db, payload.offre_id, payload.prix_mensuel_negocie)

    souscription = Souscription(
        **payload.model_dump(),
        conseiller_id=user.id,
        commission_prevue=commission_prevue,
    )
    db.add(souscription)
    await db.commit()
    await db.refresh(souscription)
    return souscription
