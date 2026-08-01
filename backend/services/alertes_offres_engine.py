# ==============================================================================
#  ALERTES OFFRES — détecte, pour chaque contrat client, si la meilleure offre
#  du catalogue est significativement moins chère que le coût actuel du
#  contrat. Ne modifie jamais le contrat directement : une `AlerteOffre`
#  'en_attente' est créée, à valider par le conseiller
#  (backend/routers/alertes_offres.py) — même principe que
#  backend/services/veille_engine.py::valider_alerte/rejeter_alerte, sauf
#  qu'ici la validation déclenche l'envoi de la proposition au client (le
#  conseiller valide avant tout envoi, jamais l'automate seul).
# ==============================================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.alerte_offre import AlerteOffre
from backend.models.client import Client
from backend.models.contrat import Contrat
from backend.models.parametre import Parametre
from backend.services import notification_engine, offres_engine

SEUIL_ECONOMIE_MENSUELLE_DEFAUT = 5.0  # €/mois — repli si Parametre absent
CLE_PARAMETRE_SEUIL = "seuil_alerte_offre_mensuel"

_MAINTENANT = lambda: datetime.now().strftime("%d/%m/%Y %H:%M")  # noqa: E731


async def _seuil_economie_mensuelle(db: AsyncSession) -> float:
    parametre = await db.get(Parametre, CLE_PARAMETRE_SEUIL)
    if parametre and parametre.valeur:
        try:
            return float(parametre.valeur)
        except ValueError:
            pass
    return SEUIL_ECONOMIE_MENSUELLE_DEFAUT


async def detecter_offres_moins_cheres(db: AsyncSession) -> list[dict]:
    """Compare le coût actuel de chaque contrat au catalogue d'offres ; au-delà
    du seuil configuré (`Parametre seuil_alerte_offre_mensuel`), crée une
    `AlerteOffre` 'en_attente' — jamais une deuxième fois pour le même couple
    (client, offre) tant que la précédente n'est pas traitée. Renvoie la liste
    des alertes créées, pour le digest admin (voir
    notification_engine.notifier_offres_moins_cheres)."""
    seuil = await _seuil_economie_mensuelle(db)

    contrats = (
        await db.execute(select(Contrat).where(Contrat.client_id.is_not(None)))
    ).scalars().all()

    alertes_existantes = (
        await db.execute(select(AlerteOffre).where(AlerteOffre.statut == "en_attente"))
    ).scalars().all()
    deja_alertees = {(a.client_id, a.offre_id) for a in alertes_existantes}

    creees: list[dict] = []
    for contrat in contrats:
        if not contrat.univers or not contrat.categorie:
            continue
        cout_actuel = float(contrat.cout_mensuel or 0)
        if cout_actuel <= 0:
            continue

        alternatives = await offres_engine.comparer_offres(
            db, contrat.univers, contrat.categorie, cout_actuel, fournisseur_exclu=contrat.fournisseur,
        )
        if not alternatives:
            continue
        meilleure = alternatives[0]
        if meilleure["economie_mensuelle"] <= seuil:
            continue
        if (contrat.client_id, meilleure["id"]) in deja_alertees:
            continue

        client = await db.get(Client, contrat.client_id)

        alerte = AlerteOffre(
            client_id=contrat.client_id,
            contrat_id=contrat.id,
            offre_id=meilleure["id"],
            cout_actuel=cout_actuel,
            cout_propose=meilleure["prix_mensuel"],
            economie_mensuelle=meilleure["economie_mensuelle"],
            economie_annuelle=meilleure["economie_annuelle"],
            statut="en_attente",
            date_detection=_MAINTENANT(),
        )
        db.add(alerte)
        deja_alertees.add((contrat.client_id, meilleure["id"]))
        creees.append({
            "client_id": contrat.client_id,
            "nom_client": f"{client.prenom} {client.nom}".strip() if client else "",
            "fournisseur": meilleure["fournisseur"],
            "nom_offre": meilleure["nom"],
            "cout_actuel": cout_actuel,
            "cout_propose": meilleure["prix_mensuel"],
            "economie_mensuelle": meilleure["economie_mensuelle"],
            "economie_annuelle": meilleure["economie_annuelle"],
        })

    await db.commit()
    return creees


def _corps_email_offre_moins_chere(prenom: str, alerte: AlerteOffre) -> str:
    return (
        f"<p>Bonjour {prenom},</p>"
        f"<p>Nous avons identifié une offre à <b>{alerte.cout_propose} €/mois</b> qui vous "
        f"ferait économiser <b>{round(alerte.economie_annuelle or 0, 2)} €/an</b> par rapport à "
        "votre contrat actuel.</p>"
        "<p>Contactez-nous pour en profiter.</p>"
        "<p>Votre conseiller.</p>"
    )


async def valider_alerte(db: AsyncSession, alerte_id: int) -> tuple[bool, str]:
    """Valide l'alerte et notifie immédiatement le client (email + SMS) — le
    conseiller déclenche cet envoi explicitement, jamais l'automate seul."""
    alerte = await db.get(AlerteOffre, alerte_id)
    if alerte is None:
        return False, "Alerte introuvable."
    if alerte.statut != "en_attente":
        return False, "Cette alerte a déjà été traitée."

    client = await db.get(Client, alerte.client_id) if alerte.client_id else None
    if client is not None:
        prenom = client.prenom or ""
        if client.email:
            notification_engine.envoyer_email(
                client.email,
                "Une offre moins chère pour vous",
                _corps_email_offre_moins_chere(prenom, alerte),
            )
        if client.telephone:
            notification_engine.envoyer_sms(
                client.telephone,
                f"Bonjour {prenom}, nous avons trouve une offre moins chere pour vous "
                f"({alerte.cout_propose} EUR/mois). Contactez votre conseiller.",
            )

    alerte.statut = "validee"
    alerte.date_traitement = _MAINTENANT()
    await db.commit()
    return True, "Alerte validée, le client a été notifié."


async def rejeter_alerte(db: AsyncSession, alerte_id: int) -> bool:
    alerte = await db.get(AlerteOffre, alerte_id)
    if alerte is None or alerte.statut != "en_attente":
        return False
    alerte.statut = "rejetee"
    alerte.date_traitement = _MAINTENANT()
    await db.commit()
    return True
