# ==============================================================================
#  DASHBOARD (IA Conseil) — vue d'ensemble conseiller (§2.5) et audit
#  anti-biais commercial réservé aux Admin (§2.6).
# ==============================================================================
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.ia_conseil import OffreConseil, Recommandation, Souscription
from backend.models.user import User
from backend.schemas.ia_conseil import (
    AlerteClientOut,
    CommissionMensuelleOut,
    DashboardIaConseilOut,
    EconomieParCategorie,
    PipelineOut,
)
from backend.services import anti_biais_engine, evenement_planifie_engine

router = APIRouter(prefix="/api/v1/dashboard", tags=["ia_conseil_dashboard"], dependencies=[Depends(get_current_user)])

STATUTS_PIPELINE = ("en_attente", "active", "resiliee", "annulee")


@router.get("/anti-biais")
async def anti_biais(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Ratio, par conseiller, de souscriptions favorisant une offre plus
    commissionnée que la mieux recommandée (§2.6) — réservé aux Admin, cette
    donnée n'a de sens qu'en vue d'ensemble équipe."""
    if user.role != "Admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs.")
    return await anti_biais_engine.auditer_biais_commercial(db)


@router.get("/ia-conseil", response_model=DashboardIaConseilOut)
async def resume_ia_conseil(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Vue d'ensemble conseiller (§2.5) : économies générées cette année,
    pipeline de souscriptions, relances planifiées à venir, commissions par
    mois. Admin voit toute l'équipe, un conseiller ne voit que son activité."""
    conseiller_filtre = None if user.role == "Admin" else user.id
    annee = date.today().year

    requete_economies = (
        select(OffreConseil.categorie_slug, func.coalesce(func.sum(Recommandation.economie_annuelle), 0))
        .select_from(Souscription)
        .join(OffreConseil, Souscription.offre_id == OffreConseil.id)
        .join(
            Recommandation,
            and_(Recommandation.session_id == Souscription.session_id, Recommandation.offre_id == Souscription.offre_id),
        )
        .where(extract("year", Souscription.date_souscription) == annee)
        .group_by(OffreConseil.categorie_slug)
    )
    if conseiller_filtre is not None:
        requete_economies = requete_economies.where(Souscription.conseiller_id == conseiller_filtre)
    lignes_economies = (await db.execute(requete_economies)).all()
    economies_par_categorie = [
        EconomieParCategorie(categorie_slug=categorie, economie_annuelle_totale=float(total))
        for categorie, total in lignes_economies
    ]
    economies_total = sum(e.economie_annuelle_totale for e in economies_par_categorie)

    requete_pipeline = select(Souscription.statut, func.count(Souscription.id)).group_by(Souscription.statut)
    if conseiller_filtre is not None:
        requete_pipeline = requete_pipeline.where(Souscription.conseiller_id == conseiller_filtre)
    lignes_pipeline = (await db.execute(requete_pipeline)).all()
    pipeline = dict.fromkeys(STATUTS_PIPELINE, 0)
    for statut, n in lignes_pipeline:
        if statut in pipeline:
            pipeline[statut] = n

    evenements = await evenement_planifie_engine.evenements_a_venir(db, conseiller_filtre)
    alertes_clients = [
        AlerteClientOut(id=e.id, type=e.type, date_prevue=e.date_prevue, client_id=e.client_id) for e in evenements
    ]

    requete_commissions = (
        select(
            func.to_char(Souscription.date_souscription, "YYYY-MM"),
            func.coalesce(func.sum(Souscription.commission_prevue), 0),
            func.coalesce(func.sum(Souscription.commission_encaissee), 0),
        )
        .where(Souscription.date_souscription.is_not(None))
        .group_by(func.to_char(Souscription.date_souscription, "YYYY-MM"))
        .order_by(func.to_char(Souscription.date_souscription, "YYYY-MM"))
    )
    if conseiller_filtre is not None:
        requete_commissions = requete_commissions.where(Souscription.conseiller_id == conseiller_filtre)
    lignes_commissions = (await db.execute(requete_commissions)).all()
    commissions_mensuelles = [
        CommissionMensuelleOut(mois=mois, prevue=float(prevue), encaissee=float(encaissee))
        for mois, prevue, encaissee in lignes_commissions
    ]

    return DashboardIaConseilOut(
        economies_ytd_total=economies_total,
        economies_ytd_par_categorie=economies_par_categorie,
        pipeline=PipelineOut(**pipeline),
        alertes_clients=alertes_clients,
        commissions_mensuelles=commissions_mensuelles,
    )
