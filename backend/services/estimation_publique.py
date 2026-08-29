"""ESTIMATION PUBLIQUE — moteur d'estimation d'économies pour la landing publique
/economiser. Non protégé par JWT : renvoie uniquement des fourchettes calibrées
sur la moyenne réelle de nos clients (recalculée toutes les 6h) ou, à défaut,
sur les moyennes marché publiques (Arcep, CRE, FFA).

Principes :
  - Pas de promesse chiffrée exacte (RGPD + DGCCRF + Meta Ads policy) :
    fourchette ±25 % autour d'une valeur typique, avec méthodologie publique.
  - Calibrage sur BDD clients réelle si l'échantillon est suffisant
    (>= ECHANTILLON_MIN_CLIENTS) dans la catégorie / tranche d'âge visée.
  - Fallback sur moyennes marché publiques (à documenter dans mentions légales).
  - Cache mémoire process-local, TTL 6h — recalcul lazy à la première requête
    après expiration (pas de tâche cron nécessaire pour l'instant).
"""
from __future__ import annotations

import asyncio
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.client import Client
from backend.models.contrat import Contrat


# ------------------------------------------------------------------------------
#  Barèmes de repli (fallback) — sources publiques à documenter dans la mention
#  légale de la landing :
#    - Télécom : Arcep, Observatoire des marchés, T4 2025
#    - Énergie : CRE, TRV + moyennes offres marché 2025
#    - Assurances : FFA, primes moyennes 2025
# ------------------------------------------------------------------------------
FALLBACK_MARCHE: dict[str, dict[str, float]] = {
    "Mobile":                {"marche_mensuel": 22.0, "notre_moyenne_mensuel": 12.5},
    "Box / Fibre":           {"marche_mensuel": 39.0, "notre_moyenne_mensuel": 27.0},
    "Pack Box + Mobile":     {"marche_mensuel": 58.0, "notre_moyenne_mensuel": 40.0},
    "Électricité":           {"marche_mensuel": 105.0, "notre_moyenne_mensuel": 82.0},
    "Gaz":                   {"marche_mensuel": 88.0, "notre_moyenne_mensuel": 70.0},
    "Assurance auto":        {"marche_mensuel": 55.0, "notre_moyenne_mensuel": 41.0},
    "Assurance habitation":  {"marche_mensuel": 22.0, "notre_moyenne_mensuel": 16.0},
    "Assurance santé":       {"marche_mensuel": 78.0, "notre_moyenne_mensuel": 58.0},
}

ECHANTILLON_MIN_CLIENTS = 30
INCERTITUDE_FOURCHETTE = 0.25  # ±25 %

TRANCHES_AGE = [
    ("18-25", 18, 26), ("26-35", 26, 36), ("36-45", 36, 46),
    ("46-55", 46, 56), ("56-65", 56, 66), ("66+",   66, 200),
]


def tranche_age(age: Optional[int]) -> Optional[str]:
    if age is None or age < 0:
        return None
    for label, lo, hi in TRANCHES_AGE:
        if lo <= age < hi:
            return label
    return None


# ------------------------------------------------------------------------------
#  Cache mémoire process-local — TTL REFRESH_INTERVAL_H heures
# ------------------------------------------------------------------------------
REFRESH_INTERVAL_H = 6

_cache: dict = {"data": None, "date": None}
_cache_lock = asyncio.Lock()


async def _recalculer_moyennes(db: AsyncSession) -> dict:
    """{categorie: {tranche_age: {'n': ..., 'mediane_mensuel': ...}}} calculé
    depuis la table `contrats` jointe à `clients` (pour récupérer l'âge)."""
    stmt = (
        select(Contrat.categorie, Client.age, Contrat.cout_mensuel)
        .join(Client, Client.id == Contrat.client_id)
        .where(Contrat.cout_mensuel > 0)
        .where(Contrat.categorie.is_not(None))
    )
    result = await db.execute(stmt)

    agg: dict[str, dict[str, list[float]]] = {}
    for categorie, age, cout in result.all():
        if not categorie:
            continue
        tr = tranche_age(age) or "tous"
        agg.setdefault(categorie, {}).setdefault(tr, []).append(float(cout))

    out: dict = {}
    for cat, tranches in agg.items():
        out[cat] = {}
        for tr, valeurs in tranches.items():
            if len(valeurs) >= ECHANTILLON_MIN_CLIENTS:
                out[cat][tr] = {
                    "n": len(valeurs),
                    "mediane_mensuel": round(statistics.median(valeurs), 2),
                    "moyenne_mensuel": round(statistics.mean(valeurs), 2),
                }
    return out


async def moyennes_avec_cache(db: AsyncSession) -> dict:
    """Retourne les moyennes, recalculées si le cache est expiré ou vide.
    Verrou async pour éviter que N requêtes concurrentes déclenchent N recalculs
    simultanés au moment d'une expiration (thundering herd)."""
    now = datetime.utcnow()
    if _cache["data"] is not None and _cache["date"] is not None:
        if now - _cache["date"] < timedelta(hours=REFRESH_INTERVAL_H):
            return _cache["data"]
    async with _cache_lock:
        # Recheck après acquisition du lock (une autre coroutine a pu recalculer entre-temps)
        if _cache["data"] is not None and _cache["date"] is not None:
            if now - _cache["date"] < timedelta(hours=REFRESH_INTERVAL_H):
                return _cache["data"]
        _cache["data"] = await _recalculer_moyennes(db)
        _cache["date"] = now
    return _cache["data"]


# ------------------------------------------------------------------------------
#  API publique du module
# ------------------------------------------------------------------------------
@dataclass
class LigneEstimation:
    categorie: str
    cout_actuel_mensuel: float
    notre_moyenne_mensuel: float
    economie_mensuelle_basse: float
    economie_mensuelle_haute: float
    economie_annuelle_typique: float
    source: str
    echantillon: int
    tranche_age_utilisee: Optional[str] = None


@dataclass
class Estimation:
    lignes: list[LigneEstimation] = field(default_factory=list)
    economie_annuelle_totale_basse: float = 0.0
    economie_annuelle_totale_haute: float = 0.0
    economie_annuelle_totale_typique: float = 0.0
    methodologie_url: str = "/economiser/methodologie"
    calculee_le: str = ""


def _ref_pour_categorie(
    categorie: str, age: Optional[int], moyennes: dict,
) -> tuple[float, str, int, Optional[str]]:
    """Renvoie (notre_moyenne_mensuel, source, taille_echantillon, tranche_utilisee).
    Priorité : (1) base client sur la tranche exacte, (2) base client tous âges,
    (3) fallback marché public."""
    tr = tranche_age(age)
    if categorie in moyennes and tr and tr in moyennes[categorie]:
        m = moyennes[categorie][tr]
        return m["mediane_mensuel"], "base_client", m["n"], tr
    if categorie in moyennes and "tous" in moyennes[categorie]:
        m = moyennes[categorie]["tous"]
        return m["mediane_mensuel"], "base_client", m["n"], "tous"
    fb = FALLBACK_MARCHE.get(categorie)
    if fb:
        return fb["notre_moyenne_mensuel"], "marche_public", 0, None
    return 0.0, "inconnu", 0, None


async def estimer(
    db: AsyncSession, depenses_actuelles: dict[str, float], age: Optional[int] = None,
) -> Estimation:
    """Point d'entrée principal — appelé par le router leads_public."""
    moyennes = await moyennes_avec_cache(db)
    est = Estimation(calculee_le=datetime.utcnow().isoformat(timespec="seconds") + "Z")

    for categorie, cout in depenses_actuelles.items():
        cout = float(cout or 0)
        if cout <= 0:
            continue
        ref, source, n, tr = _ref_pour_categorie(categorie, age, moyennes)

        if ref <= 0 or ref >= cout:
            # Le prospect paie déjà moins que notre moyenne → 0 d'économie plutôt
            # qu'un chiffre négatif (honnêteté commerciale).
            ligne = LigneEstimation(
                categorie=categorie, cout_actuel_mensuel=round(cout, 2),
                notre_moyenne_mensuel=round(ref, 2),
                economie_mensuelle_basse=0.0, economie_mensuelle_haute=0.0,
                economie_annuelle_typique=0.0,
                source=source, echantillon=n, tranche_age_utilisee=tr,
            )
        else:
            eco_mens = cout - ref
            eco_basse = eco_mens * (1 - INCERTITUDE_FOURCHETTE)
            eco_haute = eco_mens * (1 + INCERTITUDE_FOURCHETTE)
            ligne = LigneEstimation(
                categorie=categorie, cout_actuel_mensuel=round(cout, 2),
                notre_moyenne_mensuel=round(ref, 2),
                economie_mensuelle_basse=round(eco_basse, 2),
                economie_mensuelle_haute=round(eco_haute, 2),
                economie_annuelle_typique=round(eco_mens * 12, 2),
                source=source, echantillon=n, tranche_age_utilisee=tr,
            )
            est.economie_annuelle_totale_basse += eco_basse * 12
            est.economie_annuelle_totale_haute += eco_haute * 12
            est.economie_annuelle_totale_typique += eco_mens * 12

        est.lignes.append(ligne)

    est.economie_annuelle_totale_basse = round(est.economie_annuelle_totale_basse, 2)
    est.economie_annuelle_totale_haute = round(est.economie_annuelle_totale_haute, 2)
    est.economie_annuelle_totale_typique = round(est.economie_annuelle_totale_typique, 2)
    return est


async def statut_moteur(db: AsyncSession) -> dict:
    """Diagnostic — utilisable depuis /admin pour voir la couverture de notre base."""
    moyennes = await moyennes_avec_cache(db)
    return {
        "categories_calibrees_base_reelle": sorted(moyennes.keys()),
        "categories_en_fallback_marche": sorted(
            set(FALLBACK_MARCHE.keys()) - set(moyennes.keys())
        ),
        "derniere_maj": _cache["date"].isoformat() if _cache["date"] else None,
    }


def invalider_cache() -> None:
    """À appeler manuellement depuis /admin si tu veux forcer un recalcul immédiat
    (ex. après un import massif de nouveaux clients)."""
    _cache["data"] = None
    _cache["date"] = None
