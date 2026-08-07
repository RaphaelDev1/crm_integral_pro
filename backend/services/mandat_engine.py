# ==============================================================================
#  MANDAT ENGINE — création/envoi du mandat de représentation (Yousign) et
#  traitement post-signature : avance le dossier bloqué sur "mandat_a_signer",
#  finalise la conversion prospect→client si le client n'était encore qu'un
#  "client miroir" (voir prospect_conversion.py), et programme une relance de
#  suivi pour le conseiller. Factorisation du bloc autrefois inline dans
#  backend/workers/tasks.py::_telecharger_mandat_signe — appelé à la fois par
#  le webhook Yousign et par le fallback manuel
#  POST /mandats/{id}/marquer-signe (tant que la clé API Yousign n'est pas
#  configurée, voir backend/routers/dossiers.py).
# ==============================================================================
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.client import Client
from backend.models.dossier import Dossier
from backend.models.mandat import Mandat
from backend.models.prospect import Prospect
from backend.models.user import User
from backend.services import document_engine, dossier_engine, dossier_notifications, notification_engine, storage_engine
from backend.services.prospect_conversion import convertir_prospect

FORMAT_DATE = "%d/%m/%Y %H:%M"
JOURS_RELANCE_NOUVEAU_CLIENT = 3


class MandatEngineError(Exception):
    """Échec métier lors de la création/envoi du mandat."""


async def creer_et_envoyer_mandat(db: AsyncSession, dossier: Dossier) -> Mandat:
    """Crée le mandat de représentation du client rattaché au dossier, génère
    son PDF et déclenche l'envoi en signature électronique (Yousign, tâche
    Celery asynchrone — voir backend/workers/tasks.py::envoyer_mandat_signature).
    L'import de la tâche est différé pour éviter un cycle (tasks.py importe déjà
    ce module pour traiter_mandat_signe)."""
    from backend.workers.tasks import envoyer_mandat_signature

    client = await db.get(Client, dossier.client_id)
    if client is None:
        raise MandatEngineError("Client introuvable pour ce dossier.")

    try:
        pdf = document_engine.generer_pdf_mandat_representation(dossier, client)
        cle_s3 = storage_engine.upload_fichier(
            f"clients/{client.id}/mandat", "mandat", pdf, "mandat_representation.pdf"
        )
    except storage_engine.StorageError as exc:
        raise MandatEngineError(f"Stockage du mandat impossible : {exc}") from exc

    mandat = Mandat(
        client_id=client.id,
        statut="brouillon",
        pdf_url=cle_s3,
        date_creation=datetime.now().strftime(FORMAT_DATE),
    )
    db.add(mandat)
    await db.commit()
    await db.refresh(mandat)

    try:
        envoyer_mandat_signature.delay(mandat.id)
    except Exception as exc:  # noqa: BLE001 — broker Redis/Celery indisponible ou clé API absente
        # Ne bloque jamais le conseiller : le mandat existe déjà en base
        # (statut "erreur"), le bouton "Marquer signé manuellement" (fallback
        # demandé tant que Yousign n'est pas configuré) reste utilisable.
        mandat.statut = "erreur"
        mandat.notes = f"Échec de l'envoi en signature électronique : {exc}"
        await db.commit()
        await db.refresh(mandat)

    return mandat


async def traiter_mandat_signe(db: AsyncSession, mandat: Mandat, *, par: str) -> None:
    """Actions déclenchées à la signature effective d'un mandat, quelle que
    soit la voie (webhook Yousign ou fallback manuel)."""
    if not mandat.client_id:
        return

    client = await db.get(Client, mandat.client_id)
    if client is None:
        return

    dossier = (
        await db.execute(
            select(Dossier).where(Dossier.client_id == mandat.client_id, Dossier.statut == "mandat_a_signer")
        )
    ).scalars().first()

    if dossier is not None:
        try:
            await dossier_engine.transiter(
                db, dossier, "mandat_signe",
                par=par,
                commentaire="Mandat de représentation signé.",
                on_transition=lambda d, _ancien: dossier_notifications.notifier_transition(d, client),
            )
            await notification_engine.creer_notification_conseiller(
                db, dossier, f"Mandat de représentation signé par {par} — dossier #{dossier.id}."
            )
        except dossier_engine.TransitionInvalide:
            pass

    # Le prospect n'était encore rattaché qu'à un client "miroir" (voir
    # prospect_conversion.obtenir_ou_creer_client_miroir, utilisé par le
    # diagnostic) : la signature du mandat finalise la conversion, mais
    # seulement si tous les documents KYC requis sont déjà validés — sinon la
    # conversion reste en attente (bouton manuel "Convertir en client" sur la
    # fiche prospect, voir POST /prospects/{id}/convertir) pour respecter la
    # règle métier "prospect → client seulement une fois signé ET documenté".
    prospect = (
        await db.execute(
            select(Prospect).where(Prospect.client_id == mandat.client_id, Prospect.converti_at.is_(None))
        )
    ).scalars().first()

    if prospect is not None:
        complet, manquants = await dossier_engine.documents_valides_pour_client(db, mandat.client_id)
        if complet:
            conseiller_id = None
            if dossier is not None and dossier.conseiller_responsable:
                conseiller = (
                    await db.execute(select(User).where(User.nom_complet == dossier.conseiller_responsable))
                ).scalars().first()
                conseiller_id = conseiller.id if conseiller else None
            await convertir_prospect(db, prospect, par=par, conseiller_id=conseiller_id)
        elif dossier is not None:
            await dossier_engine.ajouter_note(
                db, dossier,
                f"Mandat signé mais conversion en client différée — documents manquants ou non validés : "
                f"{', '.join(manquants)}.",
                par=par,
            )
            await notification_engine.creer_notification_conseiller(
                db, dossier,
                f"Dossier #{dossier.id} : mandat signé, conversion en client en attente des documents "
                f"({', '.join(manquants)}).",
            )

    # Relance de suivi pour que le conseiller continue la gestion du nouveau
    # client jusqu'à finalisation du dossier (champs déjà branchés sur l'écran
    # "Nouvelle relance" de la fiche client — pas de nouvelle UI à inventer).
    relance = datetime.now() + timedelta(days=JOURS_RELANCE_NOUVEAU_CLIENT)
    client.date_relance = relance.strftime("%Y-%m-%d")
    client.statut_relance = "À relancer"
    await db.commit()
