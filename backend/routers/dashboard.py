# ==============================================================================
#  DASHBOARD — vue agrégée pour la page d'accueil du conseiller : relances en
#  retard/du jour/à venir (clients + prospects) et quelques KPIs. Remplace le
#  calcul fait côté Streamlit en lisant SQLite directement (src/app.py) —
#  agrégé ici en un seul appel, GET /dashboard/summary.
# ==============================================================================
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.client import Client
from backend.models.dossier import Dossier
from backend.models.prospect import Prospect
from backend.schemas.dashboard import DashboardSummaryOut, KpisOut
from backend.services import prospect_scoring

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])

# Statuts qui sortent définitivement du pipeline — le reste (y compris "actif", qui peut
# encore transiter vers "facture") compte comme "en cours" pour le KPI.
STATUTS_DOSSIER_TERMINAUX = ("facture", "echec", "annule")


def _parse_date_relance(valeur: str | None) -> date | None:
    """`date_relance` est écrit en ISO (YYYY-MM-DD) partout — les champs
    `<input type="date">` du frontend et `POST /prospects/{id}/relance-effectuee`
    produisent ce format nativement. Ne pas confondre avec le format d/m/Y
    utilisé ailleurs (dates d'action, de signature...)."""
    if not valeur:
        return None
    try:
        return date.fromisoformat(valeur.strip())
    except ValueError:
        return None


def _classer_relance(date_relance: str | None, aujourdhui: date, compteurs: dict[str, int]) -> None:
    parsee = _parse_date_relance(date_relance)
    if parsee is None:
        return
    if parsee < aujourdhui:
        compteurs["retard"] += 1
    elif parsee == aujourdhui:
        compteurs["jour"] += 1
    else:
        compteurs["venir"] += 1


@router.get("/summary", response_model=DashboardSummaryOut)
async def resume_dashboard(db: AsyncSession = Depends(get_db)):
    aujourdhui = date.today()
    compteurs = {"retard": 0, "jour": 0, "venir": 0}

    clients = (await db.execute(select(Client))).scalars().all()
    for client in clients:
        _classer_relance(client.date_relance, aujourdhui, compteurs)

    # Les prospects déjà convertis ont leur relance suivie côté Client, pas ici.
    prospects = (await db.execute(
        select(Prospect).where(Prospect.converti_at.is_(None))
    )).scalars().all()
    for prospect in prospects:
        _classer_relance(prospect.date_relance, aujourdhui, compteurs)

    contacts = await prospect_scoring.derniers_contacts(db)
    chauds = tiedes = froids = 0
    for prospect in prospects:
        score = prospect_scoring.calculer_score(prospect, contacts.get(prospect.id))
        indicateur = prospect_scoring.indicateur_score(score)
        if indicateur == "🔴 chaud":
            chauds += 1
        elif indicateur == "🟡 tiède":
            tiedes += 1
        else:
            froids += 1

    total_clients = (await db.execute(select(func.count()).select_from(Client))).scalar_one()
    dossiers_en_cours = (await db.execute(
        select(func.count()).select_from(Dossier).where(Dossier.statut.notin_(STATUTS_DOSSIER_TERMINAUX))
    )).scalar_one()

    return DashboardSummaryOut(
        relances_retard=compteurs["retard"],
        relances_jour=compteurs["jour"],
        relances_venir=compteurs["venir"],
        kpis=KpisOut(
            total_clients=total_clients,
            total_prospects=len(prospects),
            prospects_chauds=chauds,
            prospects_tiedes=tiedes,
            prospects_froids=froids,
            dossiers_en_cours=dossiers_en_cours,
        ),
    )
