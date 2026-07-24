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
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.models.client import Client
from backend.models.demarche import Demarche
from backend.models.document import Document
from backend.models.dossier import Dossier
from backend.models.mandat import Mandat
from backend.models.token_public import TokenPublic
from backend.schemas.portail_public import (
    ChampDemarchePublicOut,
    ChampsDemarchePublicUpdate,
    DemarcheAFournirOut,
    DocumentDemandeOut,
    SuiviDossierOut,
    SuiviEtape,
    TokenPublicContexte,
    UploadResultOut,
)
from backend.services import demarches_engine, dossier_engine, storage_engine, token_engine
from backend.services.kyc_engine import KycError, valider_document

router = APIRouter(prefix="/portail", tags=["portail_public"])


async def _resoudre_token(
    token: str, request: Request, db: AsyncSession
) -> TokenPublic:
    ip = request.client.host if request.client else None
    token_obj = await token_engine.valider_token(db, token, ip_appelant=ip)
    if token_obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lien invalide, expiré ou révoqué.")
    return token_obj


@router.get("/{token}", response_model=TokenPublicContexte)
async def contexte_token(
    request: Request,
    token: str = Path(..., min_length=32),
    db: AsyncSession = Depends(get_db),
):
    token_obj = await _resoudre_token(token, request, db)

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


@router.post("/{token}/documents", response_model=UploadResultOut)
async def uploader_document(
    request: Request,
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

    etapes_dict = dossier_engine.construire_timeline(dossier)
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
