# ==============================================================================
#  ALERTES_ENGINE — normalisation à 3 niveaux (info/attention/critique) des
#  alertes brutes de backend/rules_engine/alertes.py, et blocage de la
#  souscription tant qu'une alerte critique n'a pas été explicitement levée
#  (override + justification obligatoire, auditée). PLAN_IMPLEMENTATION_4_PHASES.md §2.1.
# ==============================================================================
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ia_conseil import AlerteOverride, Recommandation

NIVEAU_INFO = "info"
NIVEAU_ATTENTION = "attention"
NIVEAU_CRITIQUE = "critique"
NIVEAUX = (NIVEAU_INFO, NIVEAU_ATTENTION, NIVEAU_CRITIQUE)


def normaliser_niveau(severite: Any) -> str:
    """Une règle mal configurée (typo, valeur absente) ne doit jamais faire
    remonter une fausse alerte critique ni faire disparaître silencieusement
    une vraie alerte : tout ce qui n'est pas une valeur connue retombe sur le
    niveau le plus bas, 'info'."""
    if isinstance(severite, str) and severite in NIVEAUX:
        return severite
    return NIVEAU_INFO


def severite_normalisee(alertes: list[dict]) -> list[dict]:
    return [{**alerte, "severite": normaliser_niveau(alerte.get("severite"))} for alerte in alertes]


async def alertes_critiques_non_levees(db: AsyncSession, session_id: uuid.UUID, offre_id: uuid.UUID) -> list[dict]:
    """Alertes 'critique' de la dernière recommandation calculée pour ce
    couple (session, offre), moins celles déjà couvertes par un override
    enregistré pour ce même couple. Renvoie une liste vide si tout est levé
    (ou s'il n'y a jamais eu d'alerte)."""
    result = await db.execute(
        select(Recommandation)
        .where(Recommandation.session_id == session_id, Recommandation.offre_id == offre_id)
        .order_by(Recommandation.id.desc())
    )
    recommandation = result.scalars().first()
    if recommandation is None or not recommandation.alertes:
        return []

    critiques = [a for a in recommandation.alertes if normaliser_niveau(a.get("severite")) == NIVEAU_CRITIQUE]
    if not critiques:
        return []

    overrides = await db.execute(
        select(AlerteOverride.regle_nom).where(
            AlerteOverride.session_id == session_id, AlerteOverride.offre_id == offre_id
        )
    )
    regles_levees = {r for r in overrides.scalars().all()}

    return [a for a in critiques if a.get("regle") not in regles_levees]


async def enregistrer_override(
    db: AsyncSession,
    session_id: uuid.UUID,
    offre_id: uuid.UUID,
    regle_nom: str,
    justification: str,
    conseiller_id: int | None,
) -> AlerteOverride:
    override = AlerteOverride(
        session_id=session_id,
        offre_id=offre_id,
        regle_nom=regle_nom,
        justification=justification,
        conseiller_id=conseiller_id,
    )
    db.add(override)
    await db.flush()
    return override
