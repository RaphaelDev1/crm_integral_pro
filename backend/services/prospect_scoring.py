# ==============================================================================
#  PROSPECT SCORING — priorisation automatique des relances, porté de
#  src/prospects_engine.py::calculer_score_prospect/expliquer_score_prospect
#  (économie, ancienneté du dernier contact, satisfaction, intention de
#  rester, type de client) vers un service async utilisable par
#  backend/routers/prospects.py.
# ==============================================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.historique_action import HistoriqueAction
from backend.models.prospect import Prospect

FORMAT_DATE = "%d/%m/%Y %H:%M"

SATISFACTION_BASSE = "😡 Pas du tout"

SEUIL_SCORE_CHAUD = 150   # score >= ce seuil → 🔴 chaud
SEUIL_SCORE_TIEDE = 60    # score >= ce seuil → 🟡 tiède (sinon 🟢 froid)


def _parse_date_creation(prospect: Prospect) -> datetime | None:
    try:
        return datetime.strptime(prospect.date_creation, FORMAT_DATE)
    except (ValueError, TypeError):
        return None


def calculer_score(prospect: Prospect, dernier_contact: datetime | None = None) -> float:
    """Score de priorité d'un prospect (plus il est élevé, plus la relance est
    urgente/rentable) :

        score = economie_estimee_an*2 + jours_depuis_dernier_contact*3
              + (satisfaction_basse ? +20 : 0) + (veut_rester ? -15 : 0)
              + (type_pro ? +10 : 0)

    Si `dernier_contact` n'est pas fourni, déduit de `prospect.date_creation`.
    """
    economie = prospect.economie_estimee_an or 0.0

    if dernier_contact is None:
        dernier_contact = _parse_date_creation(prospect)
    jours = max(0, (datetime.now() - dernier_contact).days) if dernier_contact else 0

    score = (economie * 2) + (jours * 3)
    score += 20 if prospect.satisfaction_reseau == SATISFACTION_BASSE else 0
    score -= 15 if prospect.veut_rester == "Oui" else 0
    score += 10 if prospect.type_client == "Professionnel" else 0
    return round(score, 2)


def details_score(prospect: Prospect, dernier_contact: datetime | None = None) -> list[dict]:
    """Détail structuré des composantes du score (mêmes règles que
    `calculer_score`), pour affichage au conseiller."""
    economie = prospect.economie_estimee_an or 0.0

    if dernier_contact is None:
        dernier_contact = _parse_date_creation(prospect)
    jours = max(0, (datetime.now() - dernier_contact).days) if dernier_contact else 0

    details = [
        {"facteur": "Économie estimée", "poids": round(economie * 2), "valeur": f"{economie:.0f} €/an"},
        {"facteur": "Ancienneté du dernier contact", "poids": round(jours * 3), "valeur": f"{jours} j"},
    ]
    if prospect.satisfaction_reseau == SATISFACTION_BASSE:
        details.append({"facteur": "Faible satisfaction réseau", "poids": 20, "valeur": prospect.satisfaction_reseau})
    if prospect.veut_rester == "Oui":
        details.append({"facteur": "Souhaite rester chez son opérateur actuel", "poids": -15, "valeur": "Oui"})
    if prospect.type_client == "Professionnel":
        details.append({"facteur": "Client professionnel", "poids": 10, "valeur": "Professionnel"})
    return details


def indicateur_score(score: float) -> str:
    """Étiquette visuelle de température de la relance à partir du score."""
    if score >= SEUIL_SCORE_CHAUD:
        return "🔴 chaud"
    if score >= SEUIL_SCORE_TIEDE:
        return "🟡 tiède"
    return "🟢 froid"


def dernier_contact_affiche(prospect: Prospect, dernier_contact: datetime | None) -> str | None:
    """Valeur affichée au conseiller pour `Prospect.dernier_contact` : à
    défaut d'action journalisée (aucune entrée dans historique_actions), on
    retombe sur la date de création du prospect plutôt que d'afficher
    "Jamais" — un prospect fraîchement créé a bien été "contacté" ce jour-là."""
    if dernier_contact is not None:
        return dernier_contact.strftime(FORMAT_DATE)
    return prospect.date_creation


async def dernier_contact(db: AsyncSession, prospect_id: int) -> datetime | None:
    """Date du dernier contact enregistré pour ce prospect (historique
    d'audit), ou None si aucun."""
    result = await db.execute(
        select(func.max(HistoriqueAction.date_action))
        .where(HistoriqueAction.entite_type == "prospect", HistoriqueAction.entite_id == prospect_id)
    )
    valeur = result.scalar_one_or_none()
    try:
        return datetime.strptime(valeur, FORMAT_DATE) if valeur else None
    except ValueError:
        return None


async def derniers_contacts(db: AsyncSession) -> dict[int, datetime]:
    """{prospect_id: datetime du dernier contact} pour tous les prospects
    ayant au moins une entrée d'audit — une seule requête, à utiliser avant
    d'afficher une liste de prospects pour éviter le N+1 (cf. GET /prospects)."""
    result = await db.execute(
        select(HistoriqueAction.entite_id, HistoriqueAction.date_action)
        .where(HistoriqueAction.entite_type == "prospect")
    )
    derniers: dict[int, datetime] = {}
    for entite_id, date_action in result.all():
        try:
            dt = datetime.strptime(date_action, FORMAT_DATE)
        except (ValueError, TypeError):
            continue
        if entite_id not in derniers or dt > derniers[entite_id]:
            derniers[entite_id] = dt
    return derniers
