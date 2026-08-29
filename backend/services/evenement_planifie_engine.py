# ==============================================================================
#  EVENEMENT_PLANIFIE_ENGINE — planifie puis exécute les relances à date fixe
#  du sous-système IA Conseil (fin d'engagement J-60, bilan annuel, NPS J+30,
#  alerte de veille prix §2.2). PLAN_IMPLEMENTATION_4_PHASES.md §2.3.
#
#  Idempotence : `planifier_evenements_manquants` ne crée jamais deux fois le
#  même (client_id, type, date_prevue) — sûr à relancer tous les jours, même
#  pour des souscriptions déjà couvertes lors d'un run précédent.
# ==============================================================================
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ia_conseil import ClientConseil, EvenementPlanifie, Souscription
from backend.services import notification_engine

TYPE_FIN_ENGAGEMENT = "fin_engagement_J-60"
TYPE_BILAN_ANNUEL = "bilan_annuel"
TYPE_NPS_J30 = "nps_j30"
TYPE_VEILLE_ALERTE = "veille_alerte"

JOURS_AVANT_FIN_ENGAGEMENT = 60
JOURS_BILAN_ANNUEL = 365


async def planifier_evenements_manquants(db: AsyncSession) -> int:
    """Balayage quotidien : pour chaque souscription en_attente/active ayant
    fin_engagement ou date_activation renseignée, crée les EvenementPlanifie
    correspondants s'ils n'existent pas déjà. Ne couvre pas 'veille_alerte'
    (créé directement par backend/services/veille_souscriptions_engine.py,
    qui connaît déjà l'offre alternative détectée)."""
    souscriptions = (
        await db.execute(select(Souscription).where(Souscription.statut.in_(["en_attente", "active"])))
    ).scalars().all()

    existants = (
        await db.execute(select(EvenementPlanifie.client_id, EvenementPlanifie.type, EvenementPlanifie.date_prevue))
    ).all()
    deja_planifies = {(client_id, type_, date_prevue) for client_id, type_, date_prevue in existants}

    crees = 0
    for souscription in souscriptions:
        if souscription.client_id is None:
            continue

        candidats: list[tuple[str, date]] = []
        if souscription.fin_engagement:
            candidats.append((TYPE_FIN_ENGAGEMENT, souscription.fin_engagement - timedelta(days=JOURS_AVANT_FIN_ENGAGEMENT)))
        if souscription.date_activation:
            candidats.append((TYPE_BILAN_ANNUEL, souscription.date_activation + timedelta(days=JOURS_BILAN_ANNUEL)))
            candidats.append((TYPE_NPS_J30, souscription.date_activation + timedelta(days=30)))

        for type_, date_prevue in candidats:
            cle = (souscription.client_id, type_, date_prevue)
            if cle in deja_planifies:
                continue
            db.add(
                EvenementPlanifie(
                    client_id=souscription.client_id,
                    conseiller_id=souscription.conseiller_id,
                    type=type_,
                    date_prevue=date_prevue,
                    payload={"souscription_id": str(souscription.id), "categorie_slug": None},
                )
            )
            deja_planifies.add(cle)
            crees += 1

    await db.commit()
    return crees


def _email_pour_evenement(type_: str, prenom: str, payload: dict) -> tuple[str, str] | None:
    """Renvoie (sujet, corps HTML) ou None si ce type d'événement n'a pas
    d'email client associé."""
    if type_ == TYPE_FIN_ENGAGEMENT:
        corps = notification_engine.template_email_fin_engagement_conseil(prenom, payload.get("categorie_slug"))
        return "Votre engagement arrive à échéance", corps
    if type_ == TYPE_NPS_J30:
        return "Votre avis nous intéresse", notification_engine.template_email_nps_j30_conseil(prenom)
    if type_ == TYPE_VEILLE_ALERTE:
        economie = payload.get("economie_annuelle")
        corps = (
            f"<p>Bonjour {prenom},</p>"
            f"<p>Nous avons repéré une offre plus avantageuse pour vous"
            + (f", jusqu'à {economie:.0f} €/an d'économie" if economie else "")
            + ".</p><p>Votre conseiller reprendra contact avec vous.</p>"
        )
        return "Une offre plus avantageuse pour vous", corps
    return None


def _message_conseiller(type_: str, client: ClientConseil | None, payload: dict) -> str:
    nom_client = f"{client.prenom or ''} {client.nom or ''}".strip() if client else "Client"
    libelles = {
        TYPE_FIN_ENGAGEMENT: f"{nom_client} — fin d'engagement dans 60 jours, à recontacter.",
        TYPE_BILAN_ANNUEL: f"{nom_client} — bilan annuel à faire.",
        TYPE_NPS_J30: f"{nom_client} — relance satisfaction à J+30.",
        TYPE_VEILLE_ALERTE: f"{nom_client} — offre plus avantageuse détectée en veille prix.",
    }
    return libelles.get(type_, f"{nom_client} — événement planifié à traiter.")


async def executer_evenements_du_jour(db: AsyncSession) -> int:
    """Exécute (email client + notification in-app conseiller) tout événement
    dont `date_prevue` est aujourd'hui ou passée et qui n'a pas déjà été
    traité, puis le marque `execute`."""
    aujourdhui = date.today()
    evenements = (
        await db.execute(
            select(EvenementPlanifie).where(EvenementPlanifie.date_prevue <= aujourdhui, EvenementPlanifie.execute.is_(False))
        )
    ).scalars().all()

    for evenement in evenements:
        client = await db.get(ClientConseil, evenement.client_id) if evenement.client_id else None
        payload = evenement.payload or {}

        if client is not None and client.email:
            email = _email_pour_evenement(evenement.type, client.prenom or "", payload)
            if email is not None:
                sujet, corps = email
                notification_engine.envoyer_email(client.email, sujet, corps)

        if evenement.conseiller_id is not None:
            await notification_engine.creer_notification_generique(
                db,
                evenement.conseiller_id,
                _message_conseiller(evenement.type, client, payload),
                lien=f"/ia-conseil/clients/{evenement.client_id}" if evenement.client_id else None,
            )

        evenement.execute = True
        evenement.execute_le = datetime.now(timezone.utc)

    await db.commit()
    return len(evenements)


async def evenements_a_venir(db: AsyncSession, conseiller_id: int | None) -> list[EvenementPlanifie]:
    """Événements non exécutés, pour le dashboard (§2.5) — tous conseillers si
    `conseiller_id` est None (vue Admin)."""
    requete = select(EvenementPlanifie).where(EvenementPlanifie.execute.is_(False)).order_by(EvenementPlanifie.date_prevue.asc())
    if conseiller_id is not None:
        requete = requete.where(EvenementPlanifie.conseiller_id == conseiller_id)
    return list((await db.execute(requete)).scalars().all())
