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
from backend.models.contrat import Contrat
from backend.models.demarche import Demarche
from backend.models.document import Document
from backend.models.document_prospect import DocumentProspect
from backend.models.dossier import Dossier
from backend.models.facture_analyse import FactureAnalyse
from backend.models.mandat import Mandat
from backend.models.mandat_honoraires import MandatHonoraires
from backend.models.prospect import Prospect
from backend.models.token_public import TokenPublic
from backend.schemas.portail_public import (
    ChampDemarchePublicOut,
    ChampsDemarchePublicUpdate,
    ContratTelecomPublicOut,
    DemarcheAFournirOut,
    DocumentDemandeOut,
    DocumentRecuOut,
    SituationActuellePublicIn,
    SpeedtestResultatOut,
    SuiviDossierOut,
    SuiviEtape,
    TokenPublicContexte,
    UploadResultOut,
)
from backend.services import demarches_engine, dossier_engine, notification_engine, storage_engine, token_engine
from backend.services.facture_analyzer import MIME_AUTORISES_FACTURE, FactureAnalyzerError, analyser_facture
from backend.services.kyc_engine import KycError, valider_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portail", tags=["portail_public"])

MIME_AUTORISES_SPEEDTEST = {"application/pdf", "image/jpeg", "image/png", "image/webp"}

# Types de contrat télécom (mobile/box) pouvant recevoir un speedtest ou une
# situation actuelle renseignée depuis le portail public — même vocabulaire
# que TYPES_CONTRAT côté conseiller (frontend-conseiller/components/clients/ContratForm.tsx).
CATEGORIE_CONTRAT_PAR_UNIVERS = {
    "telecom_mobile": "Forfait mobile",
    "telecom_box": "Forfait box",
}
# Le tunnel /economiser (backend/routers/leads_public.py) crée ses contrats
# avec le vocabulaire de son moteur d'estimation marché ("Mobile",
# "Box / Fibre", "Pack Box + Mobile" — voir estimation_publique.FALLBACK_MARCHE)
# plutôt que celui du formulaire conseiller ci-dessus. On les inclut ici pour
# qu'un lead landing retrouve bien son contrat existant (situation actuelle,
# speedtest) au lieu d'en faire créer un second, déconnecté.
CATEGORIES_CONTRAT_TELECOM = tuple(CATEGORIE_CONTRAT_PAR_UNIVERS.values()) + (
    "Mobile", "Box / Fibre", "Pack Box + Mobile",
)
# Même dualité de vocabulaire que ci-dessus, pour l'Énergie : "Électricité"/
# "Gaz" (backend/routers/leads_public.py, landing /economiser) vs "Énergie
# électricité"/"Énergie gaz" (TYPES_CONTRAT côté conseiller, ContratForm.tsx).
CATEGORIES_CONTRAT_ENERGIE = ("Électricité", "Gaz", "Énergie électricité", "Énergie gaz")

# Catégories de ligne pour lesquelles la portabilité (conserver_numero/rio/
# numero_ligne/type_sim) a un sens — pas pour une box, voir
# renseigner_situation_actuelle. Couvre le vocabulaire conseiller
# ("Forfait mobile") et celui de la landing /economiser ("Mobile").
CATEGORIES_CONTRAT_MOBILE = ("Forfait mobile", "Mobile")

# Champs de SituationActuellePublicIn qui décrivent la personne (socle de la
# trame, voir docs/QUESTIONS_PAR_SECTEUR.md) plutôt qu'une ligne précise —
# routés vers Prospect au lieu du Contrat ciblé par la soumission, voir
# renseigner_situation_actuelle.
CHAMPS_SOCLE_PROSPECT = (
    "objectif_principal", "nb_lignes_mobiles", "qualite_reseau_mobile",
    "date_naissance", "departement_naissance", "ville_naissance",
)


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


async def _debit_deja_mesure_sur_un_contrat(
    db: AsyncSession, *, prospect_id: int | None = None, client_id: int | None = None
) -> bool:
    """Un débit peut avoir été mesuré directement sur une ligne mobile/box
    (saisie conseiller via ContratForm.tsx, ou un test soumis pour cette ligne
    précise via soumettre_speedtest) sans jamais remonter sur
    Prospect.speed_down/Client.speed_down — ne pas ignorer ce cas dans
    speedtest_fait, sous peine de redemander un test déjà disponible."""
    condition = Contrat.prospect_id == prospect_id if prospect_id is not None else Contrat.client_id == client_id
    resultat = await db.execute(
        select(Contrat.id).where(
            condition,
            Contrat.chez_nous.is_(False),
            Contrat.categorie.in_(CATEGORIES_CONTRAT_TELECOM),
            (Contrat.speed_down.is_not(None)) | (Contrat.speed_up.is_not(None)),
        ).limit(1)
    )
    return resultat.scalars().first() is not None


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
    # Plusieurs fichiers peuvent exister pour un même type (ex. plusieurs
    # factures) — voir _uploader_document_prospect, qui n'écrase jamais un
    # document existant.
    docs_par_type: dict[str, list[DocumentProspect]] = {}
    for d in docs_existants:
        docs_par_type.setdefault(d.type_document, []).append(d)

    documents_a_fournir = [
        DocumentDemandeOut(
            type_document=demande["type_document"],
            label_affiche=demande["label_affiche"],
            statut="recu" if demande["type_document"] in docs_par_type else "a_fournir",
            date_upload=docs_par_type[demande["type_document"]][-1].date_upload
            if demande["type_document"] in docs_par_type else None,
            fichiers_recus=[
                DocumentRecuOut(document_id=d.id, nom_fichier=d.nom_fichier, date_upload=d.date_upload)
                for d in docs_par_type.get(demande["type_document"], [])
            ],
        )
        for demande in DOCUMENTS_PROSPECT
    ]
    speedtest_fait = (
        bool(prospect.speed_down) or bool(prospect.speed_up) or "speedtest" in docs_par_type
        or await _debit_deja_mesure_sur_un_contrat(db, prospect_id=token_obj.prospect_id)
    )
    contrat_situation = (await db.execute(
        select(Contrat).where(
            Contrat.prospect_id == token_obj.prospect_id,
            Contrat.chez_nous.is_(False),
            Contrat.categorie.in_(CATEGORIES_CONTRAT_TELECOM),
        )
    )).scalars().first()
    # Uniquement posé par renseigner_situation_actuelle (vraie soumission du
    # prospect) — ne pas se fier à la présence de fournisseur/satisfaction_
    # reseau/veut_rester/defaut_technique, qui peuvent être remplis par
    # ailleurs (capture landing /economiser, saisie conseiller via
    # ContratForm.tsx) sans que le prospect ait rien transmis lui-même.
    situation_renseignee = bool(contrat_situation) and contrat_situation.situation_confirmee_le is not None

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
        peut_renseigner_situation=True,
        situation_renseignee=situation_renseignee,
        objectif_principal=prospect.objectif_principal,
        nb_lignes_mobiles=prospect.nb_lignes_mobiles,
        qualite_reseau_mobile=prospect.qualite_reseau_mobile,
        date_naissance=prospect.date_naissance,
        departement_naissance=prospect.departement_naissance,
        ville_naissance=prospect.ville_naissance,
        # Défensif : un objet TokenPublic construit hors ORM (tests, ou lu
        # avant le flush qui applique le défaut colonne) peut porter None ici
        # même si la colonne est NOT NULL en base — True (autonome) est le
        # comportement par défaut voulu (voir migration 0052).
        remplissage_autonome=token_obj.remplissage_autonome if token_obj.remplissage_autonome is not None else True,
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
            # Du point de vue du client, "recu" (Yousign a bien reçu sa
            # signature, vérification interne en cours) équivaut à "signe" —
            # il n'a plus rien à faire, contrairement à "a_signer" qui
            # l'inviterait à tort à signer une seconde fois.
            mandat_statut = "signe" if mandat.statut in ("recu", "signe") else "a_signer"

    mandat_honoraires_statut = None
    if dossier:
        mandat_honoraires = (await db.execute(
            select(MandatHonoraires).where(MandatHonoraires.dossier_id == dossier.id)
        )).scalar_one_or_none()
        if mandat_honoraires:
            mandat_honoraires_statut = "signe" if mandat_honoraires.statut == "signe" else "a_signer"

    dossier_soumis_fournisseur = bool(dossier) and dossier_engine.dossier_a_depasse_etape(dossier, "soumis_fournisseur")

    demarches_toutes = await demarches_engine.demarches_pour_dossier(db, dossier.id) if dossier else []
    audit_complet = demarches_engine.audit_secteur_complet(demarches_toutes)

    demarches_a_completer: list[DemarcheAFournirOut] = []
    if dossier and token_obj.peut_renseigner_demarches:
        for demarche in demarches_toutes:
            if demarche.statut != "a_generer":
                continue
            manquants = demarches_engine.champs_manquants(demarche)
            if not manquants:
                continue
            demarches_a_completer.append(_vers_demarche_a_fournir(demarche, manquants))

    speedtest_fait = (
        bool(client.speed_down) or bool(client.speed_up) or "speedtest" in docs_par_type
        or await _debit_deja_mesure_sur_un_contrat(db, client_id=token_obj.client_id)
    )

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
        audit_complet=audit_complet,
        peut_renseigner_demarches=token_obj.peut_renseigner_demarches,
        peut_transmettre_speedtest=token_obj.peut_transmettre_speedtest,
        speedtest_fait=speedtest_fait,
        peut_voir_suivi=token_obj.peut_voir_suivi and dossier is not None,
        mandat_honoraires_statut=mandat_honoraires_statut,
        dossier_soumis_fournisseur=dossier_soumis_fournisseur,
    )


def _vers_demarche_a_fournir(demarche: Demarche, champs_a_afficher: dict[str, dict] | None = None) -> DemarcheAFournirOut:
    champs_source = champs_a_afficher if champs_a_afficher is not None else (demarche.donnees_requises or {})
    return DemarcheAFournirOut(
        demarche_id=demarche.id,
        type_demarche=demarche.type_demarche,
        statut=demarche.statut,
        champs=[
            ChampDemarchePublicOut(
                cle=cle, label=infos.get("label", cle), valeur=infos.get("valeur"), requis=infos.get("requis", True),
                type=infos.get("type", "texte"), options=infos.get("options"), aide=infos.get("aide"),
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

    if type_document == "facture":
        prospect = await db.get(Prospect, token_obj.prospect_id)
        if prospect is not None:
            await notification_engine.creer_notification_prospect(
                db, prospect, f"Nouveau document transmis par {prospect.prenom or 'un prospect'} {prospect.nom or ''}."
            )

    # Détection par contenu réel (magic bytes), jamais par l'extension du nom
    # de fichier — le portail accepte les photos de facture (JPG/PNG), qui
    # sinon n'étaient jamais envoyées à l'analyse automatique (voir
    # facture_analyzer.py::MIME_AUTORISES_FACTURE).
    if type_document == "facture" and storage_engine.deviner_mime_reel(contenu) in MIME_AUTORISES_FACTURE:
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

    # La trame de questions du secteur (audit_*/portabilite) doit être
    # répondue avant l'upload de documents — voir
    # demarches_engine.audit_secteur_complet et TokenPublicContexte.audit_complet.
    # Ne s'applique pas aux tokens prospect (pas de démarche rattachée).
    dossier: Dossier | None = None
    if token_obj.prospect_id is None and token_obj.dossier_id:
        dossier = await db.get(Dossier, token_obj.dossier_id)
        if dossier is not None:
            demarches_toutes = await demarches_engine.demarches_pour_dossier(db, dossier.id)
            if not demarches_engine.audit_secteur_complet(demarches_toutes):
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "Merci de répondre d'abord aux questions sur votre situation avant d'envoyer vos documents.",
                )

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

    # La validation KYC automatique ne fixe plus jamais le statut final — un
    # document reste "en_attente" jusqu'à ce que le conseiller clique
    # "Valider"/"Rejeter" (voir DocumentsSection, dossiers/[id]/page.tsx), même
    # quand l'analyse automatique le juge conforme. On garde l'analyse pour le
    # type détecté (`type_detecte`, retourné au client mais pas persisté comme
    # motif de rejet — `Document.motif_rejet` est visible du client, il ne
    # doit afficher un motif que si le conseiller a réellement rejeté).
    # Seule une vraie erreur technique (fichier illisible/corrompu) garde le
    # statut "erreur".
    type_detecte = None
    statut_kyc = "en_attente"
    motif = None
    try:
        resultat = valider_document(contenu, fichier.filename or "document.pdf")
        type_detecte = resultat["type"]
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
        if dossier is None:
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
    if statut == "rejete":
        return f"⚠️ Document non conforme : {motif or 'motif non précisé'}. Merci de refaire l'upload."
    # "valide"/"erreur" ne sont plus jamais posés automatiquement à l'upload
    # (voir uploader_document ci-dessus) — un document tout juste envoyé est
    # toujours "en_attente", en attente de vérification par le conseiller.
    return "Document reçu, en attente de vérification par votre conseiller."


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

    signaux = await dossier_engine.signaux_timeline(db, dossier)
    etapes_dict = dossier_engine.construire_timeline(dossier, **signaux)
    etapes = [SuiviEtape(**e) for e in etapes_dict]

    return SuiviDossierOut(
        dossier_id=dossier.id,
        statut_actuel=dossier.statut,
        etapes=etapes,
        prochaine_action=_prochaine_action(dossier),
        delai_estime=_delai_estime(dossier.statut),
    )


def _prochaine_action(dossier: Dossier) -> str | None:
    statut = dossier.statut
    # "docs_recus" n'est atteint qu'une fois TOUS les documents du client
    # validés par le conseiller (voir clients.py::valider_document_client) —
    # la vérification est donc déjà terminée dès ce statut, pas "en cours".
    # `date_derniere_transition` (posée par dossier_engine.transiter) porte la
    # date ET l'heure de cette validation.
    if statut == "docs_recus":
        return (
            f"Vérification faite le {dossier.date_derniere_transition} — "
            "nous allons vous envoyer le mandat de représentation à signer."
        )
    # "soumis_fournisseur" est atteint dès la signature du mandat d'honoraires
    # (voir honoraires.py::marquer_signe_honoraires) — l'envoi effectif au
    # fournisseur reste une action à venir du conseiller à ce stade, pas déjà
    # faite : le message ne doit donc pas dire "envoyé" mais "en attente".
    if statut == "soumis_fournisseur":
        return (
            "Envoi de votre dossier au fournisseur en attente. "
            "Nous allons envoyer votre dossier complet au fournisseur."
        )
    return {
        "initie": "Votre conseiller prépare votre dossier.",
        "docs_demandes": "Merci d'uploader les documents demandés.",
        "mandat_a_signer": "Merci de signer votre mandat de représentation.",
        "mandat_signe": "Votre dossier va être envoyé au fournisseur.",
        "en_activation": "Votre nouvelle offre s'active.",
        "actif": "🎉 Tout est actif ! Bienvenue.",
    }.get(statut)


def _delai_estime(statut: str) -> str | None:
    """Estimation approximative, volontairement large (pas un engagement
    contractuel), pour tenir le client informé du temps qu'il reste — voir
    "suivi de votre dossier" côté frontend-portail. Pas de valeur pour "actif"
    (dossier terminé, plus rien à attendre)."""
    return {
        "initie": "Votre conseiller revient généralement vers vous sous 24h.",
        "docs_demandes": "La vérification démarre généralement sous 24h après réception de vos documents.",
        "docs_recus": "Vérification en cours, généralement sous 24 à 48h.",
        "mandat_a_signer": "La signature ne prend que quelques minutes une fois le lien reçu.",
        "mandat_signe": "Transmission au fournisseur généralement sous 24 à 48h.",
        "soumis_fournisseur": "Le fournisseur traite en général les dossiers sous 5 à 10 jours.",
        "en_activation": "L'activation intervient généralement sous 24 à 72h.",
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


@router.get("/{token}/contrats-telecom", response_model=list[ContratTelecomPublicOut])
async def lister_contrats_telecom(
    request: Request,
    token: str = Path(..., min_length=32),
    avec_energie: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Liste les contrats concurrents (chez_nous=False) du client ou prospect
    de ce lien. Par défaut, scope mobile/box uniquement — utilisé pour choisir
    à quel forfait un test de débit se rapporte (voir POST /{token}/speedtest,
    paramètre contrat_id) avant de le lancer, où l'énergie n'a pas de sens.
    `avec_energie=true` (utilisé par situation/page.tsx) élargit aussi aux
    contrats Énergie électricité/gaz, pour couvrir toute la trame par secteur
    (docs/QUESTIONS_PAR_SECTEUR.md)."""
    token_obj = await _resoudre_token(token, request, db)

    categories = CATEGORIES_CONTRAT_TELECOM + CATEGORIES_CONTRAT_ENERGIE if avec_energie else CATEGORIES_CONTRAT_TELECOM
    condition = (
        Contrat.prospect_id == token_obj.prospect_id
        if token_obj.prospect_id is not None
        else Contrat.client_id == token_obj.client_id
    )
    contrats = (await db.execute(
        select(Contrat).where(
            condition, Contrat.chez_nous.is_(False), Contrat.categorie.in_(categories),
        ).order_by(Contrat.id)
    )).scalars().all()
    return [
        ContratTelecomPublicOut(
            id=c.id, categorie=c.categorie, fournisseur=c.fournisseur, nom_offre=c.nom_offre,
            satisfaction_reseau=c.satisfaction_reseau, veut_rester=c.veut_rester,
            defaut_technique=c.defaut_technique, situation_renseignee=c.situation_confirmee_le is not None,
            consommation=c.consommation, date_fin_engagement=c.date_fin_engagement,
            conserver_numero=c.conserver_numero, rio=c.rio, numero_ligne=c.numero_ligne, type_sim=c.type_sim,
            chauffage_principal=c.chauffage_principal, puissance_kva=c.puissance_kva,
            option_tarifaire=c.option_tarifaire, gros_equipement_electrique=c.gros_equipement_electrique,
            usage_tv=c.usage_tv, abonnements_payants=c.abonnements_payants,
            nb_utilisateurs_streaming=c.nb_utilisateurs_streaming, usage_4k=c.usage_4k,
            teletravail=c.teletravail, interet_box_4g5g=c.interet_box_4g5g,
            telephone_fixe_utilise=c.telephone_fixe_utilise, appels_fixe_mensuels=c.appels_fixe_mensuels,
            speed_down=c.speed_down, debit_declare=c.debit_declare,
        )
        for c in contrats
    ]


async def _contrat_situation_actuelle_prospect(
    db: AsyncSession, prospect_id: int, contrat_id: int | None = None, categorie: str | None = None
) -> Contrat:
    """Le contrat concurrent (chez_nous=False, mobile OU box) qui représente
    la "situation actuelle" de ce prospect — satisfaction réseau, envie de
    rester, défaut technique, débit mesuré (voir ContratForm.tsx côté
    conseiller).

    Si le prospect a explicitement choisi une ligne (`contrat_id`, voir GET
    /{token}/contrats-telecom, même sélecteur que pour le test de débit), on
    l'utilise telle quelle. Sinon, si un `categorie` est fourni (ex. "Énergie
    électricité", "Abonnement" — voir la ligne "montant exact" par univers sur
    documents/page.tsx côté frontend-portail), on cible/crée la ligne
    concurrente de cette catégorie plutôt que de retomber sur le défaut
    mobile/box ci-dessous, pour couvrir aussi les univers hors télécom.
    Sinon (rétrocompatibilité, ou une seule ligne existante) on retombe sur la
    ligne mobile/box flaguée `ligne_principale` (migration 0041) si le
    conseiller en a désigné une, sinon la ligne existante la plus ancienne, ou
    on en crée une mobile par défaut (cas le plus fréquent pour un prospect
    pas encore client), qui devient alors la ligne principale de facto."""
    if contrat_id is not None:
        contrat = await db.get(Contrat, contrat_id)
        if contrat is None or contrat.prospect_id != prospect_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrat introuvable pour ce lien.")
        return contrat

    if categorie is not None:
        contrat = (await db.execute(
            select(Contrat).where(
                Contrat.prospect_id == prospect_id,
                Contrat.chez_nous.is_(False),
                Contrat.categorie == categorie,
            )
        )).scalars().first()
        if contrat is None:
            contrat = Contrat(
                prospect_id=prospect_id, categorie=categorie, chez_nous=False, statut_contrat="Actuel",
            )
            db.add(contrat)
        return contrat

    contrat = (await db.execute(
        select(Contrat).where(
            Contrat.prospect_id == prospect_id,
            Contrat.chez_nous.is_(False),
            Contrat.categorie.in_(CATEGORIES_CONTRAT_TELECOM),
        ).order_by(Contrat.ligne_principale.desc(), Contrat.id)
    )).scalars().first()
    if contrat is None:
        # statut_contrat="Actuel" : même convention que
        # backend/routers/leads_public.py pour qu'un contrat "situation
        # actuelle" compte dans l'estimation d'économie (voir
        # backend/routers/contrats.py::estimer_contrats).
        contrat = Contrat(
            prospect_id=prospect_id, categorie="Forfait mobile", chez_nous=False, statut_contrat="Actuel",
            ligne_principale=True,
        )
        db.add(contrat)
    return contrat


@router.post("/{token}/situation", response_model=TokenPublicContexte)
async def renseigner_situation_actuelle(
    request: Request,
    payload: SituationActuellePublicIn,
    token: str = Path(..., min_length=32),
    db: AsyncSession = Depends(get_db),
):
    """Le prospect renseigne lui-même sa situation réseau actuelle (opérateur,
    satisfaction, envie de rester, défaut technique, ainsi que la trame mobile
    de docs/QUESTIONS_PAR_SECTEUR.md — objectif principal, nombre de lignes,
    conso data, portabilité...) depuis son lien personnel — mêmes champs que
    le bloc "Situation actuelle" de ContratForm.tsx côté conseiller, mais ici
    c'est le prospect qui répond directement, avant même d'être devenu
    client. Réservé aux liens prospect (pas de dossier/client). La plupart de
    ces champs sont rattachés au contrat concurrent ciblé
    (Contrat.chez_nous=False) ; le socle (CHAMPS_SOCLE_PROSPECT) est rattaché
    au Prospect lui-même."""
    token_obj = await _resoudre_token(token, request, db)

    if token_obj.prospect_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Non disponible sur ce lien.")

    prospect = await db.get(Prospect, token_obj.prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")

    contrat = await _contrat_situation_actuelle_prospect(
        db, token_obj.prospect_id, payload.contrat_id, payload.categorie
    )
    valeurs = payload.model_dump(exclude_unset=True, exclude={"contrat_id", "categorie"})
    # Socle de la trame mobile (docs/QUESTIONS_PAR_SECTEUR.md) : posé une
    # seule fois pour la personne, pas par ligne — sur Prospect plutôt que sur
    # le Contrat ciblé par cette soumission (voir CHAMPS_SOCLE_PROSPECT).
    for champ in CHAMPS_SOCLE_PROSPECT:
        if champ in valeurs:
            setattr(prospect, champ, valeurs.pop(champ))
    if "operateur_actuel" in valeurs:
        contrat.fournisseur = valeurs.pop("operateur_actuel")
    for champ, valeur in valeurs.items():
        setattr(contrat, champ, valeur)
    # Seul point d'écriture de ce flag — voir situation_confirmee_le sur
    # backend/models/contrat.py et son usage dans _contexte_token_prospect.
    contrat.situation_confirmee_le = datetime.now()
    await db.commit()

    await notification_engine.creer_notification_prospect(
        db, prospect, f"Situation actuelle mise à jour par {prospect.prenom or 'un prospect'} {prospect.nom or ''}."
    )

    return await _contexte_token_prospect(token_obj, db)


@router.post("/{token}/speedtest", response_model=SpeedtestResultatOut)
async def soumettre_speedtest(
    request: Request,
    background_tasks: BackgroundTasks,
    token: str = Path(..., min_length=32),
    download_mbps: float | None = Form(None),
    upload_mbps: float | None = Form(None),
    ping_ms: float | None = Form(None),
    contrat_id: int | None = Form(None),
    fichier: UploadFile | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Le client soumet soit un résultat mesuré par le widget LibreSpeed
    (download_mbps/upload_mbps), soit, en repli, une capture d'écran/PDF d'un
    test tiers (nPerf, Speedtest.net...) — jamais les deux à la fois.
    `contrat_id` (optionnel) précise à quel forfait mobile/box ce débit
    mesuré correspond — voir GET /{token}/contrats-telecom, qui liste les
    contrats parmi lesquels le client choisit avant de lancer le test."""
    token_obj = await _resoudre_token(token, request, db)

    if not token_obj.peut_transmettre_speedtest:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Transmission du test de débit non autorisée.")

    contrat_cible: Contrat | None = None
    if contrat_id is not None:
        contrat_cible = await db.get(Contrat, contrat_id)
        appartient = contrat_cible is not None and (
            (token_obj.prospect_id is not None and contrat_cible.prospect_id == token_obj.prospect_id)
            or (token_obj.client_id is not None and contrat_cible.client_id == token_obj.client_id)
        )
        if not appartient:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrat introuvable pour ce lien.")

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
        if contrat_cible is not None:
            contrat_cible.speed_down = download_mbps
            contrat_cible.speed_up = upload_mbps
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
