# ==============================================================================
#  TÂCHES CELERY — validation KYC des documents uploadés (kyc_engine) et
#  envoi/téléchargement des mandats via Yousign (signature_engine). Chaque
#  tâche ouvre sa propre session DB : un worker Celery ne partage pas le
#  cycle de vie requête/réponse de FastAPI.
# ==============================================================================
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy import and_, select

from backend.core.config import settings
from backend.core.database import AsyncSessionLocal
from backend.models.client import Client
from backend.models.demarche import Demarche
from backend.models.document import Document
from backend.models.document_prospect import DocumentProspect
from backend.models.dossier import Dossier
from backend.models.ia_conseil import SessionFacture
from backend.models.mandat import Mandat
from backend.models.prospect import Prospect
from backend.services import (
    alertes_offres_engine,
    anti_biais_engine,
    catalogue_engine,
    demarches_engine,
    dossier_engine,
    dossier_notifications,
    evenement_planifie_engine,
    ia_conseil_catalogue_sync,
    ia_conseil_facture,
    ia_conseil_ws,
    kyc_engine,
    lre_engine,
    notification_engine,
    signature_engine,
    storage_engine,
    token_engine,
    veille_engine,
    veille_marche_agent,
    veille_souscriptions_engine,
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
        # reçu ; le contenu téléchargé ci-dessus n'est pas encore persisté.
        #
        # Yousign confirme que le document est signé, mais on ne le considère
        # pas encore "signe" dans notre système : comme pour les documents
        # KYC, un conseiller doit vérifier que le mandat reçu est bien rempli
        # avant de déclencher la suite (avancement du dossier, conversion
        # prospect→client) — voir backend/routers/mandats.py::valider_mandat.
        mandat.statut = "recu"
        await db.commit()

        dossier = (
            await db.execute(
                select(Dossier).where(Dossier.client_id == mandat.client_id, Dossier.statut == "mandat_a_signer")
            )
        ).scalars().first()
        if dossier is not None:
            await notification_engine.creer_notification_conseiller(
                db, dossier, f"Mandat de représentation reçu — à valider pour le dossier #{dossier.id}."
            )


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


async def _synchroniser_catalogue_ia_conseil_periodique() -> dict:
    async with AsyncSessionLocal() as db:
        resume = await ia_conseil_catalogue_sync.synchroniser_catalogue(db, ia_conseil_catalogue_sync.ADAPTERS_ACTIFS)
        await db.commit()
        return resume


@celery_app.task(name="backend.workers.tasks.synchroniser_catalogue_ia_conseil_periodique")
def synchroniser_catalogue_ia_conseil_periodique() -> dict:
    """Tâche périodique (voir `celery_app.beat_schedule`) : synchronise le
    catalogue du sous-système IA Conseil (categorie/offre isolées du CRM,
    voir models/ia_conseil.py) à partir des adapters actifs
    (ia_conseil_catalogue_sync.ADAPTERS_ACTIFS). Aucun adapter réel branché
    à ce stade (§1.4.A/D) — upsert direct en base (pas de file de validation
    admin comme ingerer_catalogue_periodique ci-dessus, périmètre distinct)."""
    return _run(_synchroniser_catalogue_ia_conseil_periodique())


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


async def _relancer_email_j1_leads_landing() -> int:
    async with AsyncSessionLocal() as db:
        prospects = (
            await db.execute(
                select(Prospect).where(
                    and_(
                        Prospect.origine.like("Landing%"),
                        Prospect.email.isnot(None),
                        Prospect.converti_at.is_(None),
                        Prospect.email_j1_envoye.is_(False),
                    )
                )
            )
        ).scalars().all()

        maintenant = datetime.now()
        n = 0
        for prospect in prospects:
            if not prospect.date_creation:
                continue
            try:
                cree_le = datetime.strptime(prospect.date_creation, "%d/%m/%Y %H:%M")
            except ValueError:
                continue
            # Fenêtre 24h-25h : la tâche tourne toutes les heures (voir
            # beat_schedule), une fenêtre d'une heure évite de rater un lead
            # entre deux exécutions sans jamais en relancer deux fois
            # (idempotence garantie par `email_j1_envoye`, pas par la fenêtre).
            age = maintenant - cree_le
            if not (timedelta(hours=24) <= age < timedelta(hours=25)):
                continue
            envoye = notification_engine.envoyer_email(
                prospect.email,
                f"{prospect.prenom}, votre estimation IA Conseil vous attend",
                notification_engine.template_email_relance_j1_landing(
                    prospect.prenom or "", prospect.economie_estimee_an or 0
                ),
            )
            if envoye:
                prospect.email_j1_envoye = True
                n += 1
        await db.commit()
        return n


@celery_app.task(name="backend.workers.tasks.relancer_email_j1_leads_landing")
def relancer_email_j1_leads_landing() -> int:
    """Tâche périodique horaire (voir `celery_app.beat_schedule`) : envoie
    l'email récap J+1 aux leads landing non convertis n'ayant pas déjà reçu
    cet email — point de contact stratégique distinct du SMS immédiat envoyé
    à la capture (backend/routers/leads_public.py, P3.2)."""
    return _run(_relancer_email_j1_leads_landing())


# ==============================================================================
#  SÉQUENCE DE NURTURING (P4.2) — 4 emails éducatifs J+2 à J+5 pour les leads
#  landing non convertis, dans la continuité de l'email récap J+1 ci-dessus.
#  Même principe de fenêtre horaire + idempotence par flag booléen que
#  _relancer_email_j1_leads_landing (voir commentaire ci-dessus).
# ==============================================================================
_SEQUENCE_NURTURING = (
    (2, "Les 3 pièges des forfaits mobile en 2026"),
    (3, "Comment changer d'opérateur sans coupure de service"),
    (4, "Le bon réflexe avant de renégocier vos factures d'énergie"),
    (5, "Dernière relance : votre estimation IA Conseil"),
)


def _construire_email_nurturing(jour: int, prospect: Prospect, url_desabonnement: str) -> str:
    prenom = prospect.prenom or ""
    if jour == 2:
        return notification_engine.template_email_nurturing_j2(prenom, url_desabonnement)
    if jour == 3:
        return notification_engine.template_email_nurturing_j3(prenom, url_desabonnement)
    if jour == 4:
        return notification_engine.template_email_nurturing_j4(prenom, url_desabonnement)
    return notification_engine.template_email_nurturing_j5(
        prenom, prospect.economie_estimee_an or 0, url_desabonnement
    )


async def _relancer_nurturing_leads_landing() -> int:
    async with AsyncSessionLocal() as db:
        prospects = (
            await db.execute(
                select(Prospect).where(
                    and_(
                        Prospect.origine.like("Landing%"),
                        Prospect.email.isnot(None),
                        Prospect.converti_at.is_(None),
                        Prospect.email_desabonne.is_(False),
                        Prospect.consentement_rgpd.is_(True),
                    )
                )
            )
        ).scalars().all()

        maintenant = datetime.now()
        n = 0
        for prospect in prospects:
            if not prospect.date_creation:
                continue
            try:
                cree_le = datetime.strptime(prospect.date_creation, "%d/%m/%Y %H:%M")
            except ValueError:
                continue
            age = maintenant - cree_le
            for jour, sujet in _SEQUENCE_NURTURING:
                if getattr(prospect, f"email_j{jour}_envoye"):
                    continue
                if not (timedelta(hours=24 * jour) <= age < timedelta(hours=24 * jour + 1)):
                    continue
                url_desabonnement = f"{settings.backend_public_base_url}/public/leads/desabonner/{prospect.ref}"
                envoye = notification_engine.envoyer_email(
                    prospect.email, sujet, _construire_email_nurturing(jour, prospect, url_desabonnement),
                )
                if envoye:
                    setattr(prospect, f"email_j{jour}_envoye", True)
                    n += 1
                # Un seul email par exécution par prospect — les fenêtres des 4 jours
                # ne se chevauchent jamais, donc au plus une itération peut matcher.
                break
        await db.commit()
        return n


@celery_app.task(name="backend.workers.tasks.relancer_nurturing_leads_landing")
def relancer_nurturing_leads_landing() -> int:
    """Tâche périodique horaire (voir `celery_app.beat_schedule`) : séquence de
    nurturing éducative J+2 à J+5 pour les leads landing non convertis (P4.2)
    — dans la continuité de l'email récap J+1
    (relancer_email_j1_leads_landing)."""
    return _run(_relancer_nurturing_leads_landing())


async def _demander_facture_prospects() -> int:
    """Envoie SMS/email demandant sa facture actuelle à tout prospect (quelle
    que soit son origine) qui n'en a pas encore transmis, pour comparer son
    contrat sans lui faire perdre de temps au téléphone — voir
    backend/services/facture_analyzer.py pour l'analyse automatique déclenchée
    à la réception (backend/routers/portail_public.py)."""
    async with AsyncSessionLocal() as db:
        prospects = (
            await db.execute(
                select(Prospect).where(
                    and_(
                        Prospect.converti_at.is_(None),
                        Prospect.demande_facture_envoyee.is_(False),
                    )
                )
            )
        ).scalars().all()

        maintenant = datetime.now()
        n = 0
        for prospect in prospects:
            if not prospect.date_creation or not (prospect.telephone or prospect.email):
                continue
            try:
                cree_le = datetime.strptime(prospect.date_creation, "%d/%m/%Y %H:%M")
            except ValueError:
                continue
            # Fenêtre 48h-49h (J+2) : laisse le temps d'un premier appel avant
            # de solliciter la facture — tâche horaire, idempotence garantie
            # par `demande_facture_envoyee`.
            age = maintenant - cree_le
            if not (timedelta(hours=48) <= age < timedelta(hours=49)):
                continue

            deja_recue = (
                await db.execute(
                    select(DocumentProspect).where(
                        DocumentProspect.prospect_id == prospect.id,
                        DocumentProspect.type_document == "facture",
                    )
                )
            ).scalars().first()
            if deja_recue is not None:
                prospect.demande_facture_envoyee = True
                continue

            token = await token_engine.generer_token_prospect_documents(db, prospect.id, cree_par="systeme")
            url = token_engine.construire_url_client(token.token, base_url=settings.portail_client_base_url)
            prenom = prospect.prenom or ""
            message = (
                f"Bonjour {prenom}, pour comparer au mieux votre contrat actuel, transmettez-nous "
                f"votre facture ici : {url} (valable 14 jours). Votre conseiller IA Conseil."
            )
            envoye = False
            if prospect.telephone:
                envoye = notification_engine.envoyer_sms(prospect.telephone, message) or envoye
            if prospect.email:
                corps = (
                    f"<p>Bonjour {prenom},</p>"
                    f"<p>Pour comparer au mieux votre contrat actuel et vous faire gagner du temps, "
                    f"pourriez-vous nous transmettre votre facture ?</p>"
                    f'<p><a href="{url}">{url}</a></p>'
                    f"<p>Ce lien est valable 14 jours.</p>"
                    f"<p>Votre conseiller IA Conseil.</p>"
                )
                envoye = notification_engine.envoyer_email(
                    prospect.email, "Transmettez-nous votre facture pour comparer", corps,
                ) or envoye
            if envoye:
                prospect.demande_facture_envoyee = True
                n += 1
        await db.commit()
        return n


@celery_app.task(name="backend.workers.tasks.demander_facture_prospects")
def demander_facture_prospects() -> int:
    """Tâche périodique horaire (voir `celery_app.beat_schedule`) : demande
    automatiquement sa facture à tout prospect actif n'en ayant pas encore
    transmis, 48h après sa création."""
    return _run(_demander_facture_prospects())


async def _auditer_biais_commercial_periodique() -> int:
    async with AsyncSessionLocal() as db:
        resultats = await anti_biais_engine.auditer_et_notifier_superviseurs(db)
        return sum(1 for r in resultats if r["au_dela_du_seuil"])


@celery_app.task(name="backend.workers.tasks.auditer_biais_commercial_periodique")
def auditer_biais_commercial_periodique() -> int:
    """Tâche périodique hebdomadaire (voir `celery_app.beat_schedule`) : calcule
    le ratio de souscriptions favorisant une offre plus commissionnée que la
    mieux recommandée, par conseiller, et notifie les comptes Admin pour tout
    conseiller au-delà du seuil configuré (§2.6, garde-fou anti-biais)."""
    return _run(_auditer_biais_commercial_periodique())


async def _detecter_alternatives_souscriptions_periodique() -> int:
    async with AsyncSessionLocal() as db:
        detectees = await veille_souscriptions_engine.detecter_alternatives_souscriptions(db)
        return len(detectees)


@celery_app.task(name="backend.workers.tasks.detecter_alternatives_souscriptions_periodique")
def detecter_alternatives_souscriptions_periodique() -> int:
    """Tâche périodique (voir `celery_app.beat_schedule`) : compare chaque
    souscription IA Conseil active proche de sa fin d'engagement au
    catalogue, dépose un EvenementPlanifie 'veille_alerte' par opportunité
    d'économie détectée au-delà du seuil configuré (§2.2)."""
    return _run(_detecter_alternatives_souscriptions_periodique())


async def _planifier_evenements_ia_conseil_periodique() -> int:
    async with AsyncSessionLocal() as db:
        return await evenement_planifie_engine.planifier_evenements_manquants(db)


@celery_app.task(name="backend.workers.tasks.planifier_evenements_ia_conseil_periodique")
def planifier_evenements_ia_conseil_periodique() -> int:
    """Tâche périodique (voir `celery_app.beat_schedule`) : crée les
    EvenementPlanifie (fin d'engagement J-60, bilan annuel, NPS J+30) pour
    toute souscription IA Conseil qui n'en a pas encore — idempotent, sûr à
    relancer tous les jours (§2.3)."""
    return _run(_planifier_evenements_ia_conseil_periodique())


async def _executer_evenements_ia_conseil_periodique() -> int:
    async with AsyncSessionLocal() as db:
        return await evenement_planifie_engine.executer_evenements_du_jour(db)


@celery_app.task(name="backend.workers.tasks.executer_evenements_ia_conseil_periodique")
def executer_evenements_ia_conseil_periodique() -> int:
    """Tâche périodique (voir `celery_app.beat_schedule`) : exécute (email
    client + notification conseiller) tout EvenementPlanifie dont la date est
    échue et marque-le traité (§2.3)."""
    return _run(_executer_evenements_ia_conseil_periodique())


async def _analyser_facture_session(facture_id: str) -> None:
    async with AsyncSessionLocal() as db:
        facture = await db.get(SessionFacture, uuid.UUID(facture_id))
        if facture is None:
            return
        facture = await ia_conseil_facture.analyser(db, facture)
        await db.commit()
        await ia_conseil_ws.publier(
            facture.session_id,
            {
                "type": "facture_analysee",
                "facture_id": str(facture.id),
                "statut": facture.statut,
                "extraction": facture.extraction,
            },
        )


@celery_app.task(
    name="backend.workers.tasks.analyser_facture_session_task", bind=True, max_retries=2, default_retry_delay=30
)
def analyser_facture_session_task(self, facture_id: str) -> None:
    """Déclenchée à l'upload d'une facture pendant une session de trame
    (§3.1, pas de planning — voir routers/ia_conseil_sessions.py) : analyse
    via facture_analyzer.py (Claude vision) et publie le résultat sur le
    canal WS de la session pour rafraîchir la vue live sans polling."""
    try:
        _run(_analyser_facture_session(facture_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _veille_marche_hebdomadaire() -> int:
    async with AsyncSessionLocal() as db:
        rapports = await veille_marche_agent.generer_rapports_toutes_categories(db)
        for rapport in rapports:
            if rapport.offres_detectees:
                await notification_engine.notifier_veille_marche_hebdomadaire(db, rapport)
        return sum(len(r.offres_detectees) for r in rapports)


@celery_app.task(name="backend.workers.tasks.veille_marche_hebdomadaire_task")
def veille_marche_hebdomadaire_task() -> int:
    """Tâche périodique hebdomadaire (voir `celery_app.beat_schedule`) :
    agent Claude (outil serveur web_search) qui scanne le web par catégorie
    pour détecter des offres pas encore au catalogue IA Conseil (§3.4).
    N'écrit jamais directement dans `offre` — chaque offre détectée attend
    une revue admin (routers/ia_conseil_catalogue.py)."""
    return _run(_veille_marche_hebdomadaire())
