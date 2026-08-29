# ==============================================================================
#  PORTAIL PUBLIC — endpoints accessibles au client via son token unique.
#
#  Option A (retenue) : pas de login. Le token est vérifié à chaque appel.
#
#  Sécurité :
#    - Rate limiting côté reverse proxy (nginx) + slowapi (à ajouter)
#    - Token vérifié à chaque requête (pas de session)
#    - IP loggée à chaque accès pour audit
#    - Pas de données sensibles remontées
# ==============================================================================
import logging
import os
import tempfile
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Path, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import AsyncSessionLocal, get_db
from backend.models.client import Client
from backend.models.demarche import Demarche
from backend.models.document import Document
from backend.models.document_prospect import DocumentProspect
from backend.models.dossier import Dossier
from backend.models.facture_analyse import FactureAnalyse
from backend.models.mandat import Mandat
from backend.models.prospect import Prospect
from backend.models.token_public import TokenPublic
from backend.schemas.portail_public import (
    ChampDemarchePublicOut,
    ChampsDemarchePublicUpdate,
    DemarcheAFournirOut,
    DocumentDemandeOut,
    SpeedtestResultatOut,
    SuiviDossierOut,
    SuiviEtape,
    TokenPublicContexte,
    UploadResultOut,
)
from backend.services import demarches_engine, dossier_engine, notification_engine, storage_engine, token_engine
from backend.services.facture_analyzer import FactureAnalyzerError, analyser_facture
from backend.services.kyc_engine import KycError, valider_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portail", tags=["portail_public"])

MIME_AUTORISES_SPEEDTEST = {"application/pdf", "image/jpeg", "image/png", "image/webp"}


async def _analyser_facture_prospect_arriere_plan(prospect_id: int, contenu: bytes) -> None:
    """Analyse automatique (Claude Haiku vision) de la facture qu'un prospect
    vient de transmettre via son lien personnel — exécutée après la réponse
    HTTP (le client n'attend pas le temps d'appel LLM). Un PDF illisible ou
    une clé API absente ne doit jamais faire échouer l'upload lui-même,
    d'où le try/except large (même logique que
    backend/routers/leads_public.py::_enrichir_lead_arriere_plan)."""
    fd, chemin_tmp = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(contenu)
        resultat = analyser_facture(chemin_tmp)
    except FactureAnalyzerError as exc:
        logger.warning("Analyse facture échouée pour le prospect %s : %s", prospect_id, exc)
        return
    finally:
        os.unlink(chemin_tmp)

    try:
        async with AsyncSessionLocal() as db:
            db.add(FactureAnalyse(
                prospect_id=prospect_id,
                **resultat,
                date_analyse=datetime.now().strftime("%d/%m/%Y %H:%M"),
                analyse_par="ia-automatique",
            ))
            await db.commit()
    except Exception as exc:
        logger.exception("Persistance de l'analyse facture échouée pour le prospect %s : %s", prospect_id, exc)


async def _resoudre_token(
    token: str, request: Request, db: AsyncSession
) -> TokenPublic:
    ip = request.client.host if request.client else None
    token_obj = await token_engine.valider_token(db, token, ip_appelant=ip)
    if token_obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lien invalide, expiré ou révoqué.")
    return token_obj


DOCUMENTS_PROSPECT = (
    {"type_document": "facture", "label_affiche": "Facture actuelle (opérateur / fournisseur)"},
)
# Le test de débit n'est volontairement PAS dans cette liste : le proposer ici,
# à côté de la facture, sur la page générique "Envoyer mes documents", faisait
# considérer le speedtest comme fait dès l'envoi des documents — le client
# n'avait alors plus jamais l'occasion de cliquer sur "Tester mon débit" (le
# vrai test en direct). Le speedtest garde son propre parcours dédié (section
# "Votre débit internet" + page /speedtest, qui offre aussi un repli par
# upload de capture via le même type_document "speedtest", voir
# soumettre_speedtest ci-dessous).


async def _contexte_token_prospect(token_obj: TokenPublic, db: AsyncSession) -> TokenPublicContexte:
    """Contexte réduit servi à un prospect (pas encore client, pas de dossier) —
    seul l'upload de facture/speedtest lui est proposé, cf.
    backend/services/token_engine.py::generer_token_prospect_documents."""
    prospect = await db.get(Prospect, token_obj.prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")

    docs_existants = (await db.execute(
        select(DocumentProspect).where(DocumentProspect.prospect_id == token_obj.prospect_id)
    )).scalars().all()
    docs_par_type = {d.type_document: d for d in docs_existants}

    documents_a_fournir = [
        DocumentDemandeOut(
            type_document=demande["type_document"],
            label_affiche=demande["label_affiche"],
            statut="recu" if demande["type_document"] in docs_par_type else "a_fournir",
            date_upload=docs_par_type[demande["type_document"]].date_upload
            if demande["type_document"] in docs_par_type else None,
        )
        for demande in DOCUMENTS_PROSPECT
    ]
    speedtest_fait = bool(prospect.speed_down) or bool(prospect.speed_up) or "speedtest" in docs_par_type

    return TokenPublicContexte(
        prenom_client=prospect.prenom or "",
        nom_client=prospect.nom or "",
        dossier_id=None,
        univers=None,
        fournisseur_cible=None,
        economie_annuelle_estimee=0.0,
        statut_dossier=None,
        conseiller_nom=prospect.cree_par,
        documents_a_fournir=documents_a_fournir,
        mandat_statut=None,
        peut_uploader_docs=token_obj.peut_uploader_docs,
        peut_signer_mandat=False,
        demarches_a_completer=[],
        peut_renseigner_demarches=False,
        peut_transmettre_speedtest=token_obj.peut_transmettre_speedtest,
        speedtest_fait=speedtest_fait,
    )


@router.get("/{token}", response_model=TokenPublicContexte)
async def contexte_token(
    request: Request,
    token: str = Path(..., min_length=32),
    db: AsyncSession = Depends(get_db),
):
    token_obj = await _resoudre_token(token, request, db)

    if token_obj.prospect_id is not None:
        return await _contexte_token_prospect(token_obj, db)

    client = await db.get(Client, token_obj.client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")

    dossier: Dossier | None = None
    if token_obj.dossier_id:
        dossier = await db.get(Dossier, token_obj.dossier_id)

    univers = dossier.univers if dossier else "telecom_mobile"
    types_requis = dossier_engine.documents_requis_pour_univers(univers)

    docs_existants = (await db.execute(
        select(Document).where(Document.client_id == client.id)
    )).scalars().all()
    docs_par_type = {d.type_document: d for d in docs_existants}

    documents_a_fournir: list[DocumentDemandeOut] = []
    for demande in types_requis:
        doc_existant = docs_par_type.get(demande["type_document"])
        if doc_existant is None:
            documents_a_fournir.append(DocumentDemandeOut(
                type_document=demande["type_document"],
                label_affiche=demande["label_affiche"],
                statut="a_fournir",
            ))
        else:
            documents_a_fournir.append(DocumentDemandeOut(
                type_document=demande["type_document"],
                label_affiche=demande["label_affiche"],
                statut=doc_existant.statut_kyc,
                motif_rejet=doc_existant.motif_rejet,
                date_upload=doc_existant.date_upload,
            ))

    mandat_statut = None
    if dossier and dossier.statut == "mandat_a_signer":
        mandat = (await db.execute(
            select(Mandat).where(Mandat.client_id == client.id).order_by(Mandat.id.desc())
        )).scalars().first()
        if mandat:
            mandat_statut = "signe" if mandat.statut == "signe" else "a_signer"

    demarches_a_completer: list[DemarcheAFournirOut] = []
    if dossier and token_obj.peut_renseigner_demarches:
        for demarche in await demarches_engine.demarches_pour_dossier(db, dossier.id):
            if demarche.statut != "a_generer":
                continue
            manquants = demarches_engine.champs_manquants(demarche)
            if not manquants:
                continue
            demarches_a_completer.append(_vers_demarche_a_fournir(demarche, manquants))

    speedtest_fait = bool(client.speed_down) or bool(client.speed_up) or "speedtest" in docs_par_type

    return TokenPublicContexte(
        prenom_client=client.prenom or "",
        nom_client=client.nom or "",
        dossier_id=dossier.id if dossier else None,
        univers=dossier.univers if dossier else None,
        fournisseur_cible=dossier.fournisseur_cible if dossier else None,
        economie_annuelle_estimee=dossier.economie_annuelle_estimee if dossier else 0.0,
        statut_dossier=dossier.statut if dossier else None,
        conseiller_nom=dossier.conseiller_responsable if dossier else client.cree_par,
        documents_a_fournir=documents_a_fournir,
        mandat_statut=mandat_statut,
        peut_uploader_docs=token_obj.peut_uploader_docs,
        peut_signer_mandat=token_obj.peut_signer_mandat,
        demarches_a_completer=demarches_a_completer,
        peut_renseigner_demarches=token_obj.peut_renseigner_demarches,
        peut_transmettre_speedtest=token_obj.peut_transmettre_speedtest,
        speedtest_fait=speedtest_fait,
    )


def _vers_demarche_a_fournir(demarche: Demarche, champs_a_afficher: dict[str, dict] | None = None) -> DemarcheAFournirOut:
    champs_source = champs_a_afficher if champs_a_afficher is not None else (demarche.donnees_requises or {})
    return DemarcheAFournirOut(
        demarche_id=demarche.id,
        type_demarche=demarche.type_demarche,
        statut=demarche.statut,
        champs=[
            ChampDemarchePublicOut(
                cle=cle, label=infos.get("label", cle), valeur=infos.get("valeur"), requis=infos.get("requis", True)
            )
            for cle, infos in champs_source.items()
        ],
    )


async def _uploader_document_prospect(
    token_obj: TokenPublic,
    type_document: str,
    contenu: bytes,
    nom_fichier: str | None,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
) -> UploadResultOut:
    """Upload d'un document (facture, speedtest) par un prospect pas encore
    client — équivalent de src/prospects_engine.py::enregistrer_document_prospect.
    Pas de validation KYC (celle-ci ne s'applique qu'aux pièces CNI/RIB/justificatif
    de domicile demandées à un client) : le document est simplement conservé pour
    le conseiller."""
    if type_document not in ("facture", "speedtest"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "type_document doit être 'facture' ou 'speedtest' pour un lien prospect.",
        )
    nom_fichier = nom_fichier or "document.pdf"
    try:
        cle_s3 = storage_engine.upload_fichier(
            prefixe=f"prospects/{token_obj.prospect_id}",
            type_document=type_document,
            contenu=contenu,
            nom_fichier=nom_fichier,
        )
    except storage_engine.StorageError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Stockage impossible : {exc}")

    document = DocumentProspect(
        prospect_id=token_obj.prospect_id,
        type_document=type_document,
        nom_fichier=nom_fichier,
        cle_stockage=cle_s3,
        mime=storage_engine.deviner_mime_reel(contenu),
        date_upload=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    if type_document == "facture" and nom_fichier.lower().endswith(".pdf"):
        background_tasks.add_task(_analyser_facture_prospect_arriere_plan, token_obj.prospect_id, contenu)

    return UploadResultOut(
        document_id=document.id,
        type_detecte=None,
        statut_kyc="recu",
        message="Document reçu, votre conseiller le consultera.",
    )


@router.post("/{token}/documents", response_model=UploadResultOut)
async def uploader_document(
    request: Request,
    background_tasks: BackgroundTasks,
    token: str = Path(..., min_length=32),
    type_document: str = "cni",
    fichier: UploadFile = None,
    db: AsyncSession = Depends(get_db),
):
    token_obj = await _resoudre_token(token, request, db)

    if not token_obj.peut_uploader_docs:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Upload de documents non autorisé.")

    if fichier is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Aucun fichier.")

    contenu = await fichier.read()
    if len(contenu) > 10 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Fichier trop volumineux (max 10 Mo).")

    if token_obj.prospect_id is not None:
        return await _uploader_document_prospect(
            token_obj, type_document, contenu, fichier.filename, db, background_tasks,
        )

    try:
        cle_s3 = storage_engine.upload_document(
            client_id=token_obj.client_id,
            type_document=type_document,
            contenu=contenu,
            nom_fichier=fichier.filename or "document.pdf",
        )
    except storage_engine.StorageError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Stockage impossible : {exc}")

    type_detecte = None
    statut_kyc = "en_attente"
    motif = None
    try:
        resultat = valider_document(contenu, fichier.filename or "document.pdf")
        type_detecte = resultat["type"]
        statut_kyc = "valide" if resultat["valide"] else "rejete"
        motif = resultat["motif_rejet"]
    except KycError as exc:
        statut_kyc = "erreur"
        motif = str(exc)

    document = Document(
        client_id=token_obj.client_id,
        type_document=type_document,
        url_stockage=cle_s3,
        statut_kyc=statut_kyc,
        motif_rejet=motif,
        date_upload=datetime.now().strftime("%d/%m/%Y %H:%M"),
        date_validation=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    if token_obj.dossier_id:
        dossier = await db.get(Dossier, token_obj.dossier_id)
        if dossier:
            await notification_engine.creer_notification_document(db, dossier)

    return UploadResultOut(
        document_id=document.id,
        type_detecte=type_detecte,
        statut_kyc=statut_kyc,
        motif_rejet=motif,
        message=_message_client(statut_kyc, motif),
    )


def _message_client(statut: str, motif: str | None) -> str:
    if statut == "valide":
        return "✅ Document reçu et validé automatiquement."
    if statut == "rejete":
        return f"⚠️ Document non conforme : {motif or 'motif non précisé'}. Merci de refaire l'upload."
    if statut == "erreur":
        return "Document reçu, en attente de vérification par votre conseiller."
    return "Document reçu."


@router.get("/{token}/suivi", response_model=SuiviDossierOut)
async def suivi_dossier(
    request: Request,
    token: str = Path(..., min_length=32),
    db: AsyncSession = Depends(get_db),
):
    token_obj = await _resoudre_token(token, request, db)

    if not token_obj.peut_voir_suivi or not token_obj.dossier_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Suivi non disponible.")

    dossier = await db.get(Dossier, token_obj.dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")

    documents_recus = (
        await db.execute(select(Document.id).where(Document.client_id == dossier.client_id).limit(1))
    ).scalar_one_or_none() is not None
    etapes_dict = dossier_engine.construire_timeline(dossier, documents_recus=documents_recus)
    etapes = [SuiviEtape(**e) for e in etapes_dict]

    return SuiviDossierOut(
        dossier_id=dossier.id,
        statut_actuel=dossier.statut,
        etapes=etapes,
        prochaine_action=_prochaine_action(dossier.statut),
    )


def _prochaine_action(statut: str) -> str | None:
    return {
        "initie": "Votre conseiller prépare votre dossier.",
        "docs_demandes": "Merci d'uploader les documents demandés.",
        "docs_recus": "Vos documents sont en cours de vérification.",
        "mandat_a_signer": "Merci de signer votre mandat de représentation.",
        "mandat_signe": "Votre dossier va être envoyé au fournisseur.",
        "soumis_fournisseur": "Dossier envoyé, en attente de validation fournisseur.",
        "en_activation": "Votre nouvelle offre s'active.",
        "actif": "🎉 Tout est actif ! Bienvenue.",
    }.get(statut)


@router.post("/{token}/demarches/{demarche_id}/champs", response_model=DemarcheAFournirOut)
async def renseigner_champs_demarche(
    request: Request,
    demarche_id: int,
    payload: ChampsDemarchePublicUpdate,
    token: str = Path(..., min_length=32),
    db: AsyncSession = Depends(get_db),
):
    """Le client complète, depuis son portail, les champs manquants d'une
    démarche (RIO, PDL/PCE, RIB...) — jamais de clé arbitraire acceptée,
    filtrée sur celles déjà déclarées dans `donnees_requises`."""
    token_obj = await _resoudre_token(token, request, db)

    if not token_obj.peut_renseigner_demarches:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Non autorisé.")

    demarche = await db.get(Demarche, demarche_id)
    if demarche is None or demarche.dossier_id != token_obj.dossier_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Démarche introuvable.")

    cles_autorisees = set((demarche.donnees_requises or {}).keys())
    valeurs_filtrees = {cle: valeur for cle, valeur in payload.valeurs.items() if cle in cles_autorisees}
    demarche = await demarches_engine.marquer_champs(db, demarche, valeurs_filtrees)
    return _vers_demarche_a_fournir(demarche)


@router.post("/{token}/speedtest", response_model=SpeedtestResultatOut)
async def soumettre_speedtest(
    request: Request,
    background_tasks: BackgroundTasks,
    token: str = Path(..., min_length=32),
    download_mbps: float | None = Form(None),
    upload_mbps: float | None = Form(None),
    ping_ms: float | None = Form(None),
    fichier: UploadFile | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Le client soumet soit un résultat mesuré par le widget LibreSpeed
    (download_mbps/upload_mbps), soit, en repli, une capture d'écran/PDF d'un
    test tiers (nPerf, Speedtest.net...) — jamais les deux à la fois."""
    token_obj = await _resoudre_token(token, request, db)

    if not token_obj.peut_transmettre_speedtest:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Transmission du test de débit non autorisée.")

    if download_mbps is not None and upload_mbps is not None:
        if token_obj.prospect_id is not None:
            prospect = await db.get(Prospect, token_obj.prospect_id)
            if prospect is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
            prospect.speed_down = download_mbps
            prospect.speed_up = upload_mbps
        else:
            client = await db.get(Client, token_obj.client_id)
            if client is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
            client.speed_down = download_mbps
            client.speed_up = upload_mbps
        await db.commit()
        if token_obj.dossier_id:
            dossier = await db.get(Dossier, token_obj.dossier_id)
            if dossier:
                await notification_engine.creer_notification_conseiller(
                    db, dossier, f"Test de débit reçu pour le dossier #{dossier.id}."
                )
        return SpeedtestResultatOut(
            speed_down=download_mbps, speed_up=upload_mbps,
            message="Test de débit enregistré, merci !",
        )

    if fichier is not None:
        contenu = await fichier.read()
        if not contenu:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Fichier vide.")
        if len(contenu) > 10 * 1024 * 1024:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Fichier trop volumineux (max 10 Mo).")

        mime_reel = storage_engine.deviner_mime_reel(contenu)
        if mime_reel not in MIME_AUTORISES_SPEEDTEST:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "Type de fichier non autorisé (PDF, JPG, PNG ou WEBP uniquement, quelle que soit l'extension).",
            )

        if token_obj.prospect_id is not None:
            resultat = await _uploader_document_prospect(
                token_obj, "speedtest", contenu, fichier.filename, db, background_tasks,
            )
            return SpeedtestResultatOut(
                document_id=resultat.document_id,
                message="Capture reçue, votre conseiller vérifiera les résultats.",
            )

        try:
            cle_s3 = storage_engine.upload_document(
                client_id=token_obj.client_id,
                type_document="speedtest",
                contenu=contenu,
                nom_fichier=fichier.filename or "speedtest.pdf",
            )
        except storage_engine.StorageError as exc:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Stockage impossible : {exc}")

        document = Document(
            client_id=token_obj.client_id,
            type_document="speedtest",
            url_stockage=cle_s3,
            statut_kyc="en_attente",
            date_upload=datetime.now().strftime("%d/%m/%Y %H:%M"),
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        if token_obj.dossier_id:
            dossier = await db.get(Dossier, token_obj.dossier_id)
            if dossier:
                await notification_engine.creer_notification_conseiller(
                    db, dossier, f"Capture de test de débit reçue pour le dossier #{dossier.id}."
                )
        return SpeedtestResultatOut(
            document_id=document.id,
            message="Capture reçue, votre conseiller vérifiera les résultats.",
        )

    raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Aucun résultat ni fichier transmis.")
