# ==============================================================================
#  AUDIT ENGINE — journal d'audit générique (insert-only), miroir de
#  src/db.py::enregistrer_action/lire_historique. Utilisé par
#  prospect_scoring.py (date de dernier contact) et prospect_conversion.py
#  (journal de conversion).
# ==============================================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.historique_action import HistoriqueAction

FORMAT_DATE = "%d/%m/%Y %H:%M"


async def enregistrer_action(
    db: AsyncSession,
    *,
    entite_type: str,
    entite_id: int,
    action: str,
    details: str | None = None,
    auteur: str | None = None,
) -> None:
    """Ajoute une ligne au journal d'audit. Ne commit pas — fait partie de la
    transaction de l'appelant."""
    db.add(HistoriqueAction(
        entite_type=entite_type, entite_id=entite_id, action=action,
        details=details, auteur=auteur,
        date_action=datetime.now().strftime(FORMAT_DATE),
    ))


async def lire_historique(db: AsyncSession, entite_type: str, entite_id: int) -> list[HistoriqueAction]:
    result = await db.execute(
        select(HistoriqueAction)
        .where(HistoriqueAction.entite_type == entite_type, HistoriqueAction.entite_id == entite_id)
        .order_by(HistoriqueAction.id.desc())
    )
    return list(result.scalars().all())
