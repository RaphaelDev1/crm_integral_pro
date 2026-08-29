# ==============================================================================
#  VEILLE_SOUSCRIPTIONS_ENGINE — détecte, pour chaque souscription IA Conseil
#  active proche de sa fin d'engagement, une offre alternative du catalogue
#  significativement moins chère. PLAN_IMPLEMENTATION_4_PHASES.md §2.2.
#
#  Équivalent, côté sous-système IA Conseil, de
#  backend/services/alertes_offres_engine.py (qui opère sur le CRM legacy
#  Contrat/Client) — même principe de seuil configurable via `Parametre`,
#  mais l'opportunité détectée est déposée comme un EvenementPlanifie
#  'veille_alerte' plutôt qu'une alerte dédiée : c'est
#  backend/services/evenement_planifie_engine.py qui se charge de l'email
#  client + la notification conseiller au moment de l'exécution (§2.3).
# ==============================================================================
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ia_conseil import EvenementPlanifie, OffreConseil, Souscription
from backend.models.parametre import Parametre
from backend.services.evenement_planifie_engine import TYPE_VEILLE_ALERTE

SEUIL_POURCENTAGE_DEFAUT = 15.0
JOURS_AVANT_FIN_ENGAGEMENT_DEFAUT = 60
CLE_PARAMETRE_SEUIL_POURCENTAGE = "seuil_veille_souscription_pct"
CLE_PARAMETRE_JOURS_AVANT_FIN = "jours_avant_fin_engagement_veille"


async def _lire_parametre_numerique(db: AsyncSession, cle: str, defaut: float) -> float:
    parametre = await db.get(Parametre, cle)
    if parametre and parametre.valeur:
        try:
            return float(parametre.valeur)
        except ValueError:
            pass
    return defaut


async def detecter_alternatives_souscriptions(db: AsyncSession) -> list[dict]:
    """Pour chaque souscription active dont la fin d'engagement tombe dans la
    fenêtre configurée, cherche la moins chère alternative active du
    catalogue sur la même catégorie ; au-delà du seuil de pourcentage
    configuré, dépose un EvenementPlanifie 'veille_alerte'. Ne recrée jamais
    une deuxième alerte en attente pour la même souscription."""
    seuil_pct = await _lire_parametre_numerique(db, CLE_PARAMETRE_SEUIL_POURCENTAGE, SEUIL_POURCENTAGE_DEFAUT)
    jours_avant = await _lire_parametre_numerique(db, CLE_PARAMETRE_JOURS_AVANT_FIN, JOURS_AVANT_FIN_ENGAGEMENT_DEFAUT)
    limite_date = date.today() + timedelta(days=jours_avant)

    souscriptions = (
        await db.execute(
            select(Souscription).where(
                Souscription.statut == "active",
                Souscription.fin_engagement.is_not(None),
                Souscription.fin_engagement <= limite_date,
            )
        )
    ).scalars().all()

    evenements_en_attente = (
        await db.execute(
            select(EvenementPlanifie.payload).where(
                EvenementPlanifie.type == TYPE_VEILLE_ALERTE, EvenementPlanifie.execute.is_(False)
            )
        )
    ).scalars().all()
    souscriptions_deja_alertees = {p.get("souscription_id") for p in evenements_en_attente if p}

    detectees: list[dict] = []
    for souscription in souscriptions:
        if str(souscription.id) in souscriptions_deja_alertees:
            continue
        if souscription.prix_mensuel_negocie is None or souscription.offre_id is None:
            continue
        prix_actuel = float(souscription.prix_mensuel_negocie)
        if prix_actuel <= 0:
            continue

        offre_actuelle = await db.get(OffreConseil, souscription.offre_id)
        if offre_actuelle is None or not offre_actuelle.categorie_slug:
            continue

        alternatives = (
            await db.execute(
                select(OffreConseil).where(
                    OffreConseil.categorie_slug == offre_actuelle.categorie_slug,
                    OffreConseil.valide.is_(True),
                    OffreConseil.id != offre_actuelle.id,
                    OffreConseil.prix_mensuel.is_not(None),
                )
            )
        ).scalars().all()
        if not alternatives:
            continue

        meilleure = min(alternatives, key=lambda o: float(o.prix_mensuel))
        prix_alternatif = float(meilleure.prix_mensuel)
        economie_pct = (prix_actuel - prix_alternatif) / prix_actuel * 100
        if economie_pct < seuil_pct:
            continue

        economie_mensuelle = prix_actuel - prix_alternatif
        payload = {
            "souscription_id": str(souscription.id),
            "offre_actuelle_id": str(offre_actuelle.id),
            "offre_alternative_id": str(meilleure.id),
            "offre_nom": meilleure.nom,
            "categorie_slug": offre_actuelle.categorie_slug,
            "economie_mensuelle": round(economie_mensuelle, 2),
            "economie_annuelle": round(economie_mensuelle * 12, 2),
            "economie_pourcentage": round(economie_pct, 1),
        }
        db.add(
            EvenementPlanifie(
                client_id=souscription.client_id,
                conseiller_id=souscription.conseiller_id,
                type=TYPE_VEILLE_ALERTE,
                date_prevue=date.today(),
                payload=payload,
            )
        )
        souscriptions_deja_alertees.add(str(souscription.id))
        detectees.append(payload)

    await db.commit()
    return detectees
