# ==============================================================================
#  IA_CONSEIL_CATALOGUE_SYNC — synchronisation planifiée du catalogue IA
#  Conseil (§1.4.A/D). Interface d'adapter réutilisable pour de vraies
#  sources partenaires (APIs affiliées Bouygues/Free/EDF via TradeDoubler,
#  Awin, Effiliation...) ; AUCUN scraping de site opérateur réel n'est câblé
#  ici — implémenter un vrai adapter suppose d'avoir des accès partenaires
#  et d'avoir validé le cadre légal (robots.txt/TOS) site par site, hors
#  périmètre de cette itération (voir PLAN_IMPLEMENTATION_4_PHASES.md §1.4.B
#  pour les contraintes scraper). En attendant de vraies sources, le CRUD
#  admin (backend/routers/ia_conseil_catalogue.py::admin_router) reste le
#  canal réel pour peupler/corriger le catalogue.
#
#  `AdapterExemple` ci-dessous ne lit qu'un jeu de données local en mémoire —
#  un point d'extension documenté, pas une intégration réelle.
# ==============================================================================
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ia_conseil import Fournisseur, OffreConseil

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OffreCandidate:
    """Offre normalisée renvoyée par un adapter, avant upsert en base."""

    fournisseur_nom: str
    nom: str
    categorie_slug: str
    prix_mensuel: float
    engagement_mois: int
    caracteristiques: dict
    source_ref: str | None = None


class AdapterCatalogue(Protocol):
    """Contrat minimal attendu de toute source catalogue (§1.4.A) : un nom
    (traçabilité dans `offre.source`) et une méthode de récupération. Une
    vraie intégration partenaire implémente `fetch_offres` en appelant son
    API (httpx, avec timeout/retry) plutôt qu'en lisant des données en dur."""

    nom: str

    async def fetch_offres(self) -> list[OffreCandidate]: ...


class AdapterExemple:
    """Point d'extension documenté (pas un adapter partenaire réel) : montre
    la forme attendue pour brancher une vraie source plus tard. Renvoie une
    liste vide par défaut pour ne jamais perturber le catalogue seedé
    manuellement (scripts/seed_ia_conseil*.py) tant qu'aucune vraie source
    n'est configurée."""

    nom = "exemple_statique"

    async def fetch_offres(self) -> list[OffreCandidate]:
        return []


async def _upsert_offre(db: AsyncSession, candidate: OffreCandidate, source: str) -> bool:
    """Renvoie True si une ligne a été créée, False si mise à jour."""
    result = await db.execute(select(Fournisseur).where(Fournisseur.nom == candidate.fournisseur_nom))
    fournisseur = result.scalar_one_or_none()
    if fournisseur is None:
        fournisseur = Fournisseur(nom=candidate.fournisseur_nom, categorie_slug=candidate.categorie_slug, affilie=True)
        db.add(fournisseur)
        await db.flush()

    result = await db.execute(
        select(OffreConseil).where(OffreConseil.fournisseur_id == fournisseur.id, OffreConseil.nom == candidate.nom)
    )
    offre = result.scalar_one_or_none()
    if offre is None:
        db.add(
            OffreConseil(
                fournisseur_id=fournisseur.id,
                categorie_slug=candidate.categorie_slug,
                nom=candidate.nom,
                prix_mensuel=candidate.prix_mensuel,
                engagement_mois=candidate.engagement_mois,
                caracteristiques=candidate.caracteristiques,
                source=source,
                source_ref=candidate.source_ref,
                valide=True,
            )
        )
        return True

    offre.prix_mensuel = candidate.prix_mensuel
    offre.engagement_mois = candidate.engagement_mois
    offre.caracteristiques = candidate.caracteristiques
    offre.source = source
    offre.source_ref = candidate.source_ref
    return False


async def synchroniser_catalogue(db: AsyncSession, adapters: list[AdapterCatalogue]) -> dict[str, dict[str, int]]:
    """Exécute chaque adapter et upsert ses offres. Ne touche jamais aux
    offres `source='manuel'` d'un autre adapter (matching par nom de
    fournisseur + nom d'offre uniquement). Ne lève jamais côté appelant : une
    erreur d'un adapter est loggée et n'empêche pas les autres de tourner."""
    resume: dict[str, dict[str, int]] = {}
    for adapter in adapters:
        crees, maj = 0, 0
        try:
            candidates = await adapter.fetch_offres()
        except Exception:
            logger.exception("Échec de synchronisation catalogue pour l'adapter %s", adapter.nom)
            resume[adapter.nom] = {"creees": 0, "mises_a_jour": 0, "erreur": 1}
            continue

        for candidate in candidates:
            if await _upsert_offre(db, candidate, source=adapter.nom):
                crees += 1
            else:
                maj += 1
        resume[adapter.nom] = {"creees": crees, "mises_a_jour": maj}

    await db.flush()
    return resume


ADAPTERS_ACTIFS: list[AdapterCatalogue] = [AdapterExemple()]
