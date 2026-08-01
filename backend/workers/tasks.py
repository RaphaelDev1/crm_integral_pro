# ==============================================================================
#  TÂCHES CELERY — validation KYC des documents uploadés (kyc_engine) et
#  envoi/téléchargement des mandats via Yousign (signature_engine). Chaque
#  tâche ouvre sa propre session DB : un worker Celery ne partage pas le
#  cycle de vie requête/réponse de FastAPI.
# ==============================================================================
from __future__ import annotations

import asyncio
from datetime import datetime

import httpx
from sqlalchemy import select

from backend.core.database import AsyncSessionLocal
from backend.models.client import Client
from backend.models.demarche import Demarche
from backend.models.document import Document
from backend.models.dossier import Dossier
from backend.models.mandat import Mandat
from backend.services import (
    alertes_offres_engine,
    catalogue_engine,
    demarches_engine,
    dossier_engine,
    dossier_notifications,
    kyc_engine,
    lre_engine,
    notification_engine,
    signature_engine,
    storage_engine,
    veille_engine,
)
from backend.workers.celery_app import celery_app

_MAINTENANT = lambda: datetime.now().strftime("%d/%m/%Y %H:%M")  # noqa: E731


def _run(coro):
    """Exécute une coroutine dans un event loop dédié. Un worker Celery
    (pool prefork ou solo) démarre chaque tâche sans loop actif : pas de
    nesting, asyncio.run() est donc sûr ici."""
    return asyncio.run(coro)


async def _telecharger(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30.0) as client:
        reponse = await client.get(url)
        reponse.raise_for_status()
        return reponse.content


async def _valider_document_kyc(document_id: int) -> None:
    async with AsyncSessionLocal() as db:
        document = await db.get(Document, document_id)
        if document is None:
            return
        try:
            contenu = await _telecharger(document.url_stockage)
            resultat = kyc_engine.valider_document(contenu, document.url_stockage)
        except (httpx.HTTPError, kyc_engine.KycError) as exc:
            document.statut_kyc = "erreur"
            document.motif_rejet = str(exc)
        else:
            document.type_document = resultat["type"]
            document.statut_kyc = "valide" if resultat["valide"] else "rejete"
            document.motif_rejet = resultat["motif_rejet"]
        document.date_validation = _MAINTENANT()
        await db.commit()


@celery_app.task(name="backend.workers.tasks.valider_document_kyc", bind=True, max_retries=3, default_retry_delay=60)
def valider_document_kyc(self, document_id: int) -> None:
    try:
        _run(_valider_document_kyc(document_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _envoyer_mandat_signature(mandat_id: int) -> None:
    async with AsyncSessionLocal() as db:
        mandat = await db.get(Mandat, mandat_id)
        if mandat is None or not mandat.pdf_url:
            return
        if mandat.statut in ("envoye", "signe", "refuse"):
            # Idempotence : une tâche rejouée (retry après crash, relance
            # manuelle) ne doit pas recréer une seconde demande de signature
            # Yousign pour un mandat déjà envoyé/traité.
            return
        client = await db.get(Client, mandat.client_id) if mandat.client_id else None
        if client is None or not client.email:
            mandat.statut = "erreur"
            mandat.notes = "Client introuvable ou sans email."
            await db.commit()
            return

        try:
            pdf = await _telecharger(mandat.pdf_url)
            resultat = await signature_engine.envoyer_mandat(
                nom_demande=f"Mandat {client.prenom} {client.nom}",
                pdf=pdf,
                nom_fichier=f"mandat_{mandat.id}.pdf",
                prenom=client.prenom or "",
                nom=client.nom or "",
                email=client.email,
                telephone=client.telephone,
            )
        except (httpx.HTTPError, signature_engine.SignatureEngineError) as exc:
            mandat.statut = "erreur"
            mandat.notes = str(exc)
            await db.commit()
            return

        mandat.yousign_signature_request_id = resultat["signature_request_id"]
        mandat.yousign_document_id = resultat["document_id"]
        mandat.statut = "envoye"
        mandat.date_envoi = _MAINTENANT()
        await db.commit()


@celery_app.task(
    name="backend.workers.tasks.envoyer_mandat_signature", bind=True, max_retries=3, default_retry_delay=60
)
def envoyer_mandat_signature(self, mandat_id: int) -> None:
    try:
        _run(_envoyer_mandat_signature(mandat_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _telecharger_mandat_signe(mandat_id: int) -> None:
    async with AsyncSessionLocal() as db:
        mandat = await db.get(Mandat, mandat_id)
        if mandat is None or not mandat.yousign_signature_request_id or not mandat.yousign_document_id:
            return
        try:
            await signature_engine.telecharger_document_signe(
                mandat.yousign_signature_request_id, mandat.yousign_document_id
            )
        except signature_engine.SignatureEngineError as exc:
            mandat.notes = str(exc)
            await db.commit()
            return
        # Stockage définitif (S3 Scaleway) à brancher une fois le bucket en
        # place (sprint 3) — pour l'instant on marque simplement le mandat
        # signé ; le contenu téléchargé ci-dessus n'est pas encore persisté.
        mandat.statut = "signe"
        mandat.date_signature = _MAINTENANT()
        await db.commit()

        # Fait avancer automatiquement le stepper du dossier correspondant —
        # évite au conseiller de devoir reporter à la main le statut après
        # une signature Yousign.
        if mandat.client_id:
            dossier = (
                await db.execute(
                    select(Dossier).where(
                        Dossier.client_id == mandat.client_id,
                        Dossier.statut == "mandat_a_signer",
                    )
                )
            ).scalars().first()
            if dossier is not None:
                client = await db.get(Client, mandat.client_id)
                try:
                    await dossier_engine.transiter(
                        db, dossier, "mandat_signe",
                        par="webhook_yousign",
                        commentaire="Mandat de représentation signé (Yousign).",
                        on_transition=lambda d, _ancien: dossier_notifications.notifier_transition(d, client),
                    )
                except dossier_engine.TransitionInvalide:
                    pass


@celery_app.task(
    name="backend.workers.tasks.telecharger_mandat_signe", bind=True, max_retries=3, default_retry_delay=60
)
def telecharger_mandat_signe(self, mandat_id: int) -> None:
    try:
        _run(_telecharger_mandat_signe(mandat_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _relancer_dossiers_stagnants() -> int:
    async with AsyncSessionLocal() as db:
        dossiers = await dossier_engine.dossiers_stagnants(db)
        for dossier in dossiers:
            client = await db.get(Client, dossier.client_id)
            dossier_notifications.notifier_relance(dossier, client)
            dossier.derniere_relance_envoyee_le = _MAINTENANT()
            dossier.notes_workflow = (dossier.notes_workflow or []) + [{
                "date": _MAINTENANT(),
                "type": "relance_auto",
                "par": "systeme",
                "texte": f"Relance automatique — dossier en attente depuis l'étape {dossier.statut}.",
            }]
        await db.commit()
        return len(dossiers)


@celery_app.task(name="backend.workers.tasks.relancer_dossiers_stagnants")
def relancer_dossiers_stagnants() -> int:
    """Tâche périodique (voir `celery_app.beat_schedule`) : relance par
    email/SMS tout dossier resté trop longtemps sur un même statut."""
    return _run(_relancer_dossiers_stagnants())


async def _generer_document_demarche(demarche_id: int) -> None:
    async with AsyncSessionLocal() as db:
        demarche = await db.get(Demarche, demarche_id)
        if demarche is None:
            return
        try:
            await demarches_engine.generer_document(db, demarche)
        except demarches_engine.DemarcheEngineError as exc:
            demarche.statut = "echouee"
            demarche.notes = str(exc)
            await db.commit()


@celery_app.task(
    name="backend.workers.tasks.generer_document_demarche", bind=True, max_retries=3, default_retry_delay=60
)
def generer_document_demarche(self, demarche_id: int) -> None:
    try:
        _run(_generer_document_demarche(demarche_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _envoyer_demarche_lre(demarche_id: int) -> None:
    async with AsyncSessionLocal() as db:
        demarche = await db.get(Demarche, demarche_id)
        if demarche is None or not demarche.document_url:
            return
        if demarche.statut in ("envoyee", "accusee"):
            # Idempotence : une tâche rejouée ne doit pas redéclencher une
            # seconde LRE (facturée et légalement tracée) pour une démarche
            # déjà envoyée.
            return
        dossier = await db.get(Dossier, demarche.dossier_id)
        client = await db.get(Client, dossier.client_id) if dossier else None
        if client is None or not client.email:
            demarche.statut = "echouee"
            demarche.notes = "Client introuvable ou sans email."
            await db.commit()
            return

        try:
            pdf = storage_engine.telecharger_document(demarche.document_url)
            resultat = await lre_engine.envoyer_lre(
                destinataire={"prenom": client.prenom or "", "nom": client.nom or "", "email": client.email},
                sujet=f"Démarche {demarche.type_demarche} — dossier #{demarche.dossier_id}",
                pdf=pdf,
                nom_fichier=f"{demarche.type_demarche}_{demarche.id}.pdf",
            )
        except (storage_engine.StorageError, lre_engine.LreEngineError) as exc:
            demarche.statut = "echouee"
            demarche.notes = str(exc)
            await db.commit()
            return

        demarche.preuve_envoi = resultat["lre_id"]
        demarche.statut = "envoyee"
        demarche.date_envoi = _MAINTENANT()
        await db.commit()


@celery_app.task(name="backend.workers.tasks.envoyer_demarche_lre", bind=True, max_retries=3, default_retry_delay=60)
def envoyer_demarche_lre(self, demarche_id: int) -> None:
    try:
        _run(_envoyer_demarche_lre(demarche_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _verifier_accuses_lre_en_attente() -> int:
    async with AsyncSessionLocal() as db:
        demarches = (
            await db.execute(select(Demarche).where(Demarche.statut == "envoyee"))
        ).scalars().all()
        n = 0
        for demarche in demarches:
            if not demarche.preuve_envoi:
                continue
            try:
                statut = await lre_engine.verifier_statut_lre(demarche.preuve_envoi)
            except lre_engine.LreEngineError:
                continue
            if statut.get("statut") in ("remise", "distribue", "accuse_reception"):
                demarche.statut = "accusee"
                demarche.date_accuse = _MAINTENANT()
                try:
                    preuve = await lre_engine.telecharger_preuve_depot(demarche.preuve_envoi)
                    demarche.preuve_url = storage_engine.upload_fichier(
                        f"dossiers/{demarche.dossier_id}/demarches", "preuve_lre", preuve, "preuve.pdf"
                    )
                except (lre_engine.LreEngineError, storage_engine.StorageError):
                    pass
                n += 1
        await db.commit()
        return n


@celery_app.task(name="backend.workers.tasks.verifier_accuses_lre_en_attente")
def verifier_accuses_lre_en_attente() -> int:
    """Tâche périodique (voir `celery_app.beat_schedule`) : AR24 ne garantit
    pas de webhook aussi fiable que Yousign pour ce cas d'usage — le polling
    régulier est le repli le plus sûr par défaut."""
    return _run(_verifier_accuses_lre_en_attente())


async def _lancer_veille_periodique() -> int:
    async with AsyncSessionLocal() as db:
        alertes = await veille_engine.lancer_veille(db)
        if alertes:
            await notification_engine.notifier_changement_prix(db, alertes)
        return len(alertes)


@celery_app.task(name="backend.workers.tasks.lancer_veille_periodique")
def lancer_veille_periodique() -> int:
    """Tâche périodique (voir `celery_app.beat_schedule`) : relève les prix
    des sources actives (scraping Playwright), remplace le script cron/schtasks
    externe src/veille_prix_engine.py. Ne modifie jamais le catalogue
    directement — une alerte 'en_attente' est créée par changement détecté,
    à valider dans Admin > Veille prix."""
    return _run(_lancer_veille_periodique())


async def _ingerer_catalogue_periodique() -> dict:
    async with AsyncSessionLocal() as db:
        resume = await catalogue_engine.ingerer_toutes_sources_actives(db)
        await notification_engine.notifier_nouvelles_offres_staging(db, resume)
        return resume


@celery_app.task(name="backend.workers.tasks.ingerer_catalogue_periodique")
def ingerer_catalogue_periodique() -> dict:
    """Tâche périodique (voir `celery_app.beat_schedule`) : ingère les sources
    catalogue actives (scraping + extraction LLM), remplace le script cron/
    schtasks externe src/catalogue_engine.py. Ne modifie jamais le catalogue
    directement — chaque offre détectée attend une validation admin dans
    Admin > Catalogue > Offres détectées."""
    return _run(_ingerer_catalogue_periodique())


async def _detecter_offres_moins_cheres_periodique() -> int:
    async with AsyncSessionLocal() as db:
        alertes = await alertes_offres_engine.detecter_offres_moins_cheres(db)
        if alertes:
            await notification_engine.notifier_offres_moins_cheres(db, alertes)
        return len(alertes)


@celery_app.task(name="backend.workers.tasks.detecter_offres_moins_cheres_periodique")
def detecter_offres_moins_cheres_periodique() -> int:
    """Tâche périodique (voir `celery_app.beat_schedule`) : compare le contrat
    actif de chaque client au catalogue d'offres, crée une alerte 'en_attente'
    par opportunité d'économie détectée au-delà du seuil configuré — à valider
    dans Admin > Alertes offres avant tout envoi au client."""
    return _run(_detecter_offres_moins_cheres_periodique())


async def _envoyer_digest_quotidien() -> dict:
    async with AsyncSessionLocal() as db:
        # Le résumé hebdomadaire (comptage prospects/clients, économies
        # totales) est ajouté au digest du lundi uniquement, plutôt que de
        # dupliquer une deuxième entrée de planification comme le faisait
        # le script cron d'origine (0 8 * * * + 0 8 * * 1).
        resume_hebdo = datetime.now().weekday() == 0
        return await notification_engine.envoyer_digest_quotidien(db, resume_hebdo=resume_hebdo)


@celery_app.task(name="backend.workers.tasks.envoyer_digest_quotidien")
def envoyer_digest_quotidien() -> dict:
    """Tâche périodique (voir `celery_app.beat_schedule`) : digest matinal
    admin (relances du jour + fins d'engagement + résumé hebdo le lundi),
    remplace le script cron/schtasks externe src/notifications.py."""
    return _run(_envoyer_digest_quotidien())
