# ==============================================================================
#  CROSS_SELL_ENGINE — suggestions inter-catégories à partir des sessions et
#  souscriptions déjà connues d'un client. PLAN_IMPLEMENTATION_4_PHASES.md §2.4.
#
#  Règles Python fixes (pas le DSL JSON de rules_engine/ — ce ne sont pas des
#  règles catalogue par catégorie mais des règles inter-catégories globales) :
#  aucune ne doit jamais lever d'exception si la question source n'a pas été
#  posée par la trame (foyer/catégorie non couverts au MVP) — `dict.get()`
#  partout, silence si absent.
# ==============================================================================
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ia_conseil import OffreConseil, SessionTrame, Souscription

TYPE_CONVERGENCE = "convergence"
TYPE_CONSEIL = "conseil"


def _roaming_frequent(reponses: dict) -> bool:
    return reponses.get("roaming_ue") == "Souvent" or reponses.get("roaming_hors_ue") == "Souvent"


def _conso_energie_forte_avec_teletravail(reponses: dict) -> bool:
    # Clés hypothétiques (la trame énergie du MVP peut ne pas les poser) :
    # 'conso_kwh_annuelle' (nombre) et 'teletravail' (booléen ou "Oui"/"Non").
    # `.get()` renvoie None si absente -> comparaison toujours sûre.
    conso = reponses.get("conso_kwh_annuelle")
    teletravail = reponses.get("teletravail")
    conso_forte = isinstance(conso, (int, float)) and conso > 8000
    return conso_forte and teletravail in (True, "Oui", "oui")


def _suggestion_convergence(paires: list[tuple[Souscription, OffreConseil]]) -> dict | None:
    fournisseur_par_categorie: dict[str, uuid.UUID] = {}
    for _souscription, offre in paires:
        if offre.categorie_slug and offre.fournisseur_id and offre.categorie_slug not in fournisseur_par_categorie:
            fournisseur_par_categorie[offre.categorie_slug] = offre.fournisseur_id

    fournisseur_mobile = fournisseur_par_categorie.get("mobile")
    fournisseur_box = fournisseur_par_categorie.get("box")
    if fournisseur_mobile and fournisseur_box and fournisseur_mobile != fournisseur_box:
        return {
            "type": TYPE_CONVERGENCE,
            "categorie_source": None,
            "message": "Mobile et box souscrits chez deux opérateurs différents — proposer une offre convergente.",
        }
    return None


def _suggestion_roaming(sessions: list[SessionTrame]) -> dict | None:
    for session in sessions:
        if session.categorie_slug == "mobile" and _roaming_frequent(session.reponses or {}):
            return {
                "type": TYPE_CONSEIL,
                "categorie_source": "mobile",
                "message": "Client voyageur fréquent — proposer une assurance voyage annuelle.",
            }
    return None


def _suggestion_renovation(sessions: list[SessionTrame]) -> dict | None:
    for session in sessions:
        if session.categorie_slug not in ("energie_elec", "energie_gaz"):
            continue
        if _conso_energie_forte_avec_teletravail(session.reponses or {}):
            return {
                "type": TYPE_CONSEIL,
                "categorie_source": session.categorie_slug,
                "message": "Consommation énergétique élevée et télétravail — orienter vers un diagnostic rénovation.",
            }
    return None


async def suggestions_cross_sell(db: AsyncSession, client_id: uuid.UUID) -> list[dict]:
    paires = (
        await db.execute(
            select(Souscription, OffreConseil)
            .join(OffreConseil, Souscription.offre_id == OffreConseil.id)
            .where(Souscription.client_id == client_id)
        )
    ).all()
    sessions = (await db.execute(select(SessionTrame).where(SessionTrame.client_id == client_id))).scalars().all()

    suggestions = [
        _suggestion_convergence(list(paires)),
        _suggestion_roaming(list(sessions)),
        _suggestion_renovation(list(sessions)),
    ]
    return [s for s in suggestions if s is not None]
