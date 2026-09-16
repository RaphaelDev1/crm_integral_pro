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
from backend.models.parametre import Parametre
from backend.models.prospect import Prospect
from backend.models.user import User
from backend.services import document_engine, dossier_engine, dossier_notifications, notification_engine, storage_engine
from backend.services.prospect_conversion import convertir_prospect

FORMAT_DATE = "%d/%m/%Y %H:%M"
JOURS_RELANCE_NOUVEAU_CLIENT = 3


class MandatEngineError(Exception):
    """Échec métier lors de la création/envoi du mandat."""


async def charger_branding(db: AsyncSession, client: Client, user: User) -> dict:
    """Charge l'habillage (logo, couleurs, société, conseiller) remis sur les
    PDF client — factorisation du bloc jusqu'ici dupliqué inline dans
    backend/routers/dossiers.py::obtenir_pdf_restitution, désormais partagé
    avec les mandats (représentation et honoraires, voir generer_mandat et
    backend/routers/honoraires.py)."""
    async def _parametre(cle: str) -> str | None:
        p = await db.get(Parametre, cle)
        return p.valeur if p else None

    logo_bytes = None
    cle_logo = await _parametre("pdf_logo_cle_stockage")
    if cle_logo:
        try:
            logo_bytes = storage_engine.telecharger_document(cle_logo)
        except storage_engine.StorageError:
            logo_bytes = None

    # Conseiller à afficher sur le PDF : le propriétaire de la fiche client
    # s'il est renseigné (conseiller_id), sinon celui qui génère le PDF.
    conseiller = user
    if client.conseiller_id is not None and client.conseiller_id != user.id:
        conseiller_proprietaire = await db.get(User, client.conseiller_id)
        if conseiller_proprietaire is not None:
            conseiller = conseiller_proprietaire

    return {
        "nom_societe": await _parametre("nom_societe"),
        "couleur_primaire_hex": await _parametre("pdf_couleur_primaire_hex"),
        "couleur_accent_hex": await _parametre("pdf_couleur_accent_hex"),
        "logo_bytes": logo_bytes,
        "conseiller_nom": conseiller.nom_complet,
        "conseiller_telephone": conseiller.telephone,
    }


async def generer_mandat(db: AsyncSession, dossier: Dossier, user: User) -> Mandat:
    """Crée le mandat de représentation du client rattaché au dossier et génère
    son PDF, sans déclencher l'envoi en signature — le conseiller doit pouvoir
    relire le PDF ("Voir le PDF généré") avant qu'il ne parte chez le client.
    L'envoi effectif se fait ensuite via `envoyer_mandat_en_signature`."""
    client = await db.get(Client, dossier.client_id)
    if client is None:
        raise MandatEngineError("Client introuvable pour ce dossier.")

    try:
        branding = await charger_branding(db, client, user)
        pdf = document_engine.generer_pdf_mandat_representation(dossier, client, branding)
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
    return mandat


async def envoyer_mandat_en_signature(db: AsyncSession, mandat: Mandat) -> Mandat:
    """Déclenche l'envoi en signature électronique (Yousign, tâche Celery
    asynchrone — voir backend/workers/tasks.py::envoyer_mandat_signature) d'un
    mandat déjà généré (brouillon relu par le conseiller, ou brouillon en
    erreur qu'on retente). L'import de la tâche est différé pour éviter un
    cycle (tasks.py importe déjà ce module pour traiter_mandat_signe)."""
    from backend.workers.tasks import envoyer_mandat_signature

    if mandat.statut not in ("brouillon", "erreur"):
        raise MandatEngineError("Ce mandat a déjà été envoyé en signature.")
    if not mandat.pdf_url:
        raise MandatEngineError("Le PDF du mandat n'a pas été généré.")

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

    # Filtré sur `Dossier.statut == "mandat_a_signer"` pour ne cibler que le
    # dossier réellement en attente de cette signature (un client peut avoir
    # plusieurs dossiers, sur des univers différents à des étapes
    # différentes) — passer à un statut ultérieur ("mandat_signe") sans être
    # passé par "mandat_a_signer" violerait la machine à états stricte de
    # toute façon (voir TRANSITIONS_AUTORISEES). Si le dossier n'a pas encore
    # été avancé manuellement jusque "mandat_a_signer", cette transition ne
    # se déclenche pas ici — mais la timeline elle-même n'en dépend plus (voir
    # dossier_engine.construire_timeline / signaux_timeline, qui lit
    # directement Mandat.statut) : l'étape "Mandat de représentation signé"
    # s'affiche donc correctement même sans cette transition.
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
