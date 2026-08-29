# ==============================================================================
#  CLIENTS — CRUD, protégé par JWT (get_current_user).
# ==============================================================================
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.client import Client
from backend.models.document import Document
from backend.models.dossier import Dossier
from backend.models.facture_analyse import FactureAnalyse
from backend.models.mandat import Mandat
from backend.models.mandat_honoraires import MandatHonoraires
from backend.models.prospect import Prospect
from backend.models.user import User
from backend.schemas.briefing import ClientBriefingOut, DocumentOut, DocumentStatutUpdate
from backend.schemas.client import ClientCreate, ClientOut, ClientUpdate, RelanceUpdate
from backend.schemas.historique_action import HistoriqueActionOut
from backend.services import audit_engine, notification_engine, reference_engine, token_engine
from backend.services.ia_conseil_bridge import obtenir_ou_creer_client_conseil
from backend.services.storage_engine import StorageError, supprimer_document, url_signee

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(get_current_user)])


def _verifier_acces(client: Client, user: User) -> None:
    """Seul le conseiller propriétaire de la fiche (celui qui l'a créée ou
    obtenue par conversion d'un prospect) ou un Admin peut y accéder.
    `conseiller_id` NULL (fiches créées avant l'introduction de cette colonne)
    reste transitoirement accessible à tous les conseillers."""
    if user.role == "Admin":
        return
    if client.conseiller_id is not None and client.conseiller_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette fiche client appartient à un autre conseiller.")


@router.get("", response_model=list[ClientOut])
async def lister_clients(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Exclut les clients "miroirs" (voir prospect_conversion.obtenir_ou_creer_client_miroir) :
    # une ligne clients existe déjà pour porter le Dossier créé pendant le diagnostic, mais
    # tant que le prospect qui la référence n'est pas officiellement converti (converti_at
    # NULL), ce n'est pas encore un vrai client pour le conseiller — voir demande produit
    # "le diagnostic ne doit créer qu'un prospect".
    non_miroir = ~exists(
        select(Prospect.id).where(Prospect.client_id == Client.id, Prospect.converti_at.is_(None))
    )
    query = select(Client).where(non_miroir).order_by(Client.id.desc())
    if user.role != "Admin":
        query = query.where((Client.conseiller_id == user.id) | (Client.conseiller_id.is_(None)))
    result = await db.execute(query)
    return result.scalars().all()


async def _documents_client(db: AsyncSession, client_id: int) -> list[DocumentOut]:
    result_docs = await db.execute(
        select(Document).where(Document.client_id == client_id).order_by(Document.id.desc())
    )
    documents: list[DocumentOut] = []
    for doc in result_docs.scalars().all():
        try:
            url = url_signee(doc.url_stockage)
        except StorageError:
            logger.warning("URL signée indisponible pour le document %s (client %s)", doc.id, client_id)
            continue
        documents.append(DocumentOut(
            id=doc.id, type_document=doc.type_document, statut_kyc=doc.statut_kyc,
            motif_rejet=doc.motif_rejet, date_upload=doc.date_upload, url=url,
        ))
    return documents


@router.get("/{client_id}/documents", response_model=list[DocumentOut])
async def documents_client(client_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    _verifier_acces(client, user)
    return await _documents_client(db, client_id)


@router.delete("/{client_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_document_client(
    client_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Supprime un document transmis par erreur (mauvais fichier, doublon) —
    le conseiller peut alors renvoyer le lien de collecte du dossier."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    _verifier_acces(client, user)

    document = await db.get(Document, document_id)
    if document is None or document.client_id != client_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document introuvable.")

    try:
        supprimer_document(document.url_stockage)
    except StorageError:
        logger.warning("Suppression S3 échouée pour le document %s (client %s)", document_id, client_id)

    await audit_engine.enregistrer_action(
        db, entite_type="client", entite_id=client_id,
        action="Document supprimé", details=document.type_document,
        auteur=user.nom_complet,
    )
    await db.delete(document)
    await db.commit()


@router.patch("/{client_id}/documents/{document_id}/statut", response_model=DocumentOut)
async def valider_document_client(
    client_id: int,
    document_id: int,
    payload: DocumentStatutUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Validation/rejet manuel d'un document par le conseiller, en plus de la
    validation automatique KYC. Un rejet crée un signalement (notification
    in-app) pour le conseiller responsable du dossier le plus récent du client."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    _verifier_acces(client, user)

    document = await db.get(Document, document_id)
    if document is None or document.client_id != client_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document introuvable.")

    document.statut_kyc = payload.statut_kyc
    document.motif_rejet = payload.motif_rejet if payload.statut_kyc == "rejete" else None
    document.date_validation = datetime.now().strftime("%d/%m/%Y %H:%M")

    await audit_engine.enregistrer_action(
        db, entite_type="client", entite_id=client_id,
        action="Document validé" if payload.statut_kyc == "valide" else "Document rejeté",
        details=payload.motif_rejet or document.type_document,
        auteur=user.nom_complet,
    )

    if payload.statut_kyc == "rejete":
        dossier = (
            await db.execute(
                select(Dossier).where(Dossier.client_id == client_id).order_by(Dossier.id.desc())
            )
        ).scalars().first()
        if dossier is not None:
            label = document.type_document or "Document"
            message = f"Document « {label} » rejeté" + (f" : {payload.motif_rejet}" if payload.motif_rejet else "")
            await notification_engine.creer_notification_conseiller(db, dossier, message)

    await db.commit()

    url = url_signee(document.url_stockage)
    return DocumentOut(
        id=document.id, type_document=document.type_document, statut_kyc=document.statut_kyc,
        motif_rejet=document.motif_rejet, date_upload=document.date_upload, url=url,
    )


@router.get("/{client_id}/historique", response_model=list[HistoriqueActionOut])
async def historique_client(client_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    _verifier_acces(client, user)
    return await audit_engine.lire_historique(db, "client", client_id)


@router.post("/{client_id}/ia-conseil-client", response_model=dict)
async def obtenir_ia_conseil_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Crée (ou réutilise) le ClientConseil IA Conseil rattaché à ce client —
    utilisé par l'étape "Trame" du diagnostic pour pouvoir lancer des sessions
    de trame adaptative (voir backend/services/ia_conseil_bridge.py)."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    _verifier_acces(client, user)
    client_conseil = await obtenir_ou_creer_client_conseil(db, client, "client", conseiller_id=user.id)
    await db.commit()
    return {"id": str(client_conseil.id)}


@router.post("/{client_id}/token-portail", response_model=dict)
async def generer_lien_portail(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Génère un lien unique à envoyer au client (SMS/email) pour qu'il accède
    à son portail sans se connecter — rattaché à son dossier en cours s'il en
    a un, sinon générique (voir backend/services/token_engine.py)."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    _verifier_acces(client, user)

    result_d = await db.execute(
        select(Dossier).where(Dossier.client_id == client_id).order_by(Dossier.id.desc())
    )
    dossiers = result_d.scalars().all()
    dossier_en_cours = next(
        (d for d in dossiers if d.statut not in ("actif", "echec", "annule")), None
    ) or (dossiers[0] if dossiers else None)

    token = await token_engine.generer_token(
        db,
        client_id=client_id,
        dossier_id=dossier_en_cours.id if dossier_en_cours else None,
        cree_par=user.username,
    )

    url = token_engine.construire_url_client(token.token, base_url=settings.portail_client_base_url)
    return {
        "token": token.token,
        "url": url,
        "expire_le": token.date_expiration,
        "message_sms_suggere": (
            f"Bonjour, voici votre lien personnel pour accéder à votre espace : "
            f"{url} (valable 30 jours). Votre conseiller."
        ),
    }


@router.get("/{client_id}/briefing", response_model=ClientBriefingOut)
async def briefing_client(client_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Vue agrégée à consulter avant d'appeler un client : ses informations,
    son dossier de souscription en cours et la dernière facture analysée —
    pour que le conseiller ait le maximum d'informations en un seul appel."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    _verifier_acces(client, user)

    result_d = await db.execute(
        select(Dossier).where(Dossier.client_id == client_id).order_by(Dossier.id.desc())
    )
    dossiers = result_d.scalars().all()
    dossier_en_cours = next(
        (d for d in dossiers if d.statut not in ("actif", "echec", "annule")), None
    ) or (dossiers[0] if dossiers else None)

    result_f = await db.execute(
        select(FactureAnalyse)
        .where(FactureAnalyse.client_id == client_id)
        .order_by(FactureAnalyse.id.desc())
        .limit(1)
    )
    derniere_facture = result_f.scalar_one_or_none()

    mandat_representation = (
        await db.execute(
            select(Mandat).where(Mandat.client_id == client_id).order_by(Mandat.id.desc()).limit(1)
        )
    ).scalar_one_or_none()

    mandat_honoraires = None
    if dossier_en_cours is not None:
        mandat_honoraires = (
            await db.execute(
                select(MandatHonoraires).where(MandatHonoraires.dossier_id == dossier_en_cours.id)
            )
        ).scalar_one_or_none()

    documents = await _documents_client(db, client_id)

    return ClientBriefingOut(
        client=client,
        dossier_en_cours=dossier_en_cours,
        derniere_facture=derniere_facture,
        nb_dossiers=len(dossiers),
        mandat_representation=mandat_representation,
        mandat_honoraires=mandat_honoraires,
        documents=documents,
    )


@router.get("/{client_id}", response_model=ClientOut)
async def obtenir_client(client_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    _verifier_acces(client, user)
    return client


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
async def creer_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    donnees = payload.model_dump()
    donnees["ref"] = await reference_engine.generer_ref_client(db)
    client = Client(
        **donnees,
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
        cree_par=user.nom_complet,
        conseiller_id=user.id,
    )
    db.add(client)
    await db.flush()
    await audit_engine.enregistrer_action(
        db, entite_type="client", entite_id=client.id,
        action="Création client", auteur=user.nom_complet,
    )
    await db.commit()
    await db.refresh(client)
    return client


@router.put("/{client_id}", response_model=ClientOut)
async def maj_client(
    client_id: int,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Réservé aux Admin : une fois une fiche client enregistrée, le conseiller
    ne peut plus modifier ses informations (voir clients/[id]/page.tsx, champs
    grisés) — seule la relance (POST /clients/{id}/relance) reste ouverte au
    conseiller propriétaire. `ref` est immuable même pour un Admin (numéro de
    dossier interne, ne doit plus bouger une fois la fiche créée)."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    if user.role != "Admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Fiche client verrouillée — modification réservée à un responsable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        if champ == "ref":
            continue
        setattr(client, champ, valeur)
    await audit_engine.enregistrer_action(
        db, entite_type="client", entite_id=client_id,
        action="Modification", auteur=user.nom_complet,
    )
    await db.commit()
    await db.refresh(client)
    return client


@router.post("/{client_id}/relance", response_model=ClientOut)
async def programmer_relance(
    client_id: int,
    payload: RelanceUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Programmer/mettre à jour la relance reste ouvert au conseiller
    propriétaire (et à l'Admin) même après verrouillage de la fiche — c'est le
    suivi courant du client, distinct de la modification de ses informations."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    _verifier_acces(client, user)
    if payload.date_relance is not None:
        client.date_relance = payload.date_relance
    if payload.statut_relance is not None:
        client.statut_relance = payload.statut_relance
    await audit_engine.enregistrer_action(
        db, entite_type="client", entite_id=client_id,
        action="Relance programmée", details=payload.date_relance, auteur=user.nom_complet,
    )
    await db.commit()
    await db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    _verifier_acces(client, user)
    await audit_engine.enregistrer_action(
        db, entite_type="client", entite_id=client_id,
        action="Suppression", details=f"{client.prenom or ''} {client.nom or ''}".strip(),
        auteur=user.nom_complet,
    )
    await db.delete(client)
    await db.commit()
