# ==============================================================================
#  PROSPECTS — CRUD, protégé par JWT (get_current_user).
# ==============================================================================
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.document_prospect import DocumentProspect
from backend.models.facture_analyse import FactureAnalyse
from backend.models.prospect import Prospect
from backend.models.user import User
from backend.schemas.client import ClientOut
from backend.schemas.document_prospect import DocumentProspectOut
from backend.schemas.dossier import EnvoiLienClient
from backend.schemas.facture import FactureClientOut
from backend.schemas.historique_action import HistoriqueActionOut
from backend.schemas.prospect import (
    ContacterTelephoneIn,
    ProspectCreate,
    ProspectOut,
    ProspectUpdate,
    ScoreProspectOut,
)
from backend.services import audit_engine, notification_engine, prospect_scoring, reference_engine, token_engine
from backend.services.ia_conseil_bridge import obtenir_ou_creer_client_conseil
from backend.services.prospect_conversion import ProspectDejaConverti, convertir_prospect, obtenir_ou_creer_client_miroir
from backend.services.storage_engine import StorageError, supprimer_document, url_signee

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prospects", tags=["prospects"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ProspectOut])
async def lister_prospects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prospect).order_by(Prospect.id.desc()))
    prospects = result.scalars().all()
    contacts = await prospect_scoring.derniers_contacts(db)
    for prospect in prospects:
        dernier = contacts.get(prospect.id)
        prospect.score = prospect_scoring.calculer_score(prospect, dernier)
        prospect.dernier_contact = prospect_scoring.dernier_contact_affiche(prospect, dernier)
    return prospects


@router.get("/{prospect_id}", response_model=ProspectOut)
async def obtenir_prospect(prospect_id: int, db: AsyncSession = Depends(get_db)):
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    dernier_contact = await prospect_scoring.dernier_contact(db, prospect_id)
    prospect.score = prospect_scoring.calculer_score(prospect, dernier_contact)
    prospect.dernier_contact = prospect_scoring.dernier_contact_affiche(prospect, dernier_contact)
    return prospect


@router.get("/{prospect_id}/score", response_model=ScoreProspectOut)
async def score_prospect(prospect_id: int, db: AsyncSession = Depends(get_db)):
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    dernier_contact = await prospect_scoring.dernier_contact(db, prospect_id)
    score = prospect_scoring.calculer_score(prospect, dernier_contact)
    return ScoreProspectOut(
        score=score,
        indicateur=prospect_scoring.indicateur_score(score),
        details=prospect_scoring.details_score(prospect, dernier_contact),
    )


@router.post("/{prospect_id}/convertir", response_model=ClientOut)
async def convertir_en_client(
    prospect_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    try:
        return await convertir_prospect(db, prospect, par=user.nom_complet)
    except ProspectDejaConverti as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.post("/{prospect_id}/client-miroir", response_model=ClientOut)
async def obtenir_client_miroir(
    prospect_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Crée (ou réutilise) le client "miroir" du prospect sans finaliser la
    conversion — utilisé par le diagnostic pour créer un dossier avant que le
    prospect ne soit officiellement converti (la conversion se déclenche
    désormais à la signature du mandat, voir mandat_engine.traiter_mandat_signe,
    pas à la génération de la restitution)."""
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    if prospect.converti_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Le prospect {prospect_id} a déjà été converti.")
    client = await obtenir_ou_creer_client_miroir(db, prospect, par=user.nom_complet)
    await db.commit()
    await db.refresh(client)
    return client


@router.post("/{prospect_id}/ia-conseil-client", response_model=dict)
async def obtenir_ia_conseil_client(
    prospect_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Crée (ou réutilise) le ClientConseil IA Conseil rattaché à ce prospect —
    utilisé par l'étape "Trame" du diagnostic pour pouvoir lancer des sessions
    de trame adaptative (voir backend/services/ia_conseil_bridge.py)."""
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    client_conseil = await obtenir_ou_creer_client_conseil(db, prospect, "prospect", conseiller_id=user.id)
    await db.commit()
    return {"id": str(client_conseil.id)}


@router.post("/{prospect_id}/token-documents", response_model=dict)
async def generer_lien_documents_prospect(
    prospect_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Génère un lien à envoyer au prospect (SMS/email) pour qu'il transmette
    lui-même sa facture/son test de débit, avant même sa conversion en client."""
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")

    token = await token_engine.generer_token_prospect_documents(
        db, prospect_id, cree_par=user.username,
    )

    url = token_engine.construire_url_client(token.token, base_url=settings.portail_client_base_url)
    return {
        "token": token.token,
        "url": url,
        "expire_le": token.date_expiration,
        "message_sms_suggere": (
            f"Bonjour, voici votre lien personnel pour nous transmettre votre facture "
            f"et/ou votre test de débit : {url} (valable 14 jours). Votre conseiller."
        ),
    }


@router.get("/{prospect_id}/factures-analysees", response_model=list[FactureClientOut])
async def factures_analysees_prospect(prospect_id: int, db: AsyncSession = Depends(get_db)):
    """Analyses de factures (télécom/énergie/assurance) déclenchées
    automatiquement à l'upload d'une facture par le prospect via son lien de
    collecte de documents (voir backend/routers/portail_public.py)."""
    result = await db.execute(
        select(FactureAnalyse)
        .where(FactureAnalyse.prospect_id == prospect_id)
        .order_by(FactureAnalyse.id.desc())
    )
    return result.scalars().all()


@router.get("/{prospect_id}/documents", response_model=list[DocumentProspectOut])
async def documents_prospect(prospect_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DocumentProspect)
        .where(DocumentProspect.prospect_id == prospect_id)
        .order_by(DocumentProspect.id.desc())
    )
    documents: list[DocumentProspectOut] = []
    for doc in result.scalars().all():
        try:
            url = url_signee(doc.cle_stockage)
        except StorageError:
            logger.warning("URL signée indisponible pour le document %s (prospect %s)", doc.id, prospect_id)
            continue
        documents.append(DocumentProspectOut(
            id=doc.id, prospect_id=doc.prospect_id, type_document=doc.type_document,
            nom_fichier=doc.nom_fichier, mime=doc.mime, date_upload=doc.date_upload, url=url,
        ))
    return documents


@router.delete("/{prospect_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_document_prospect(
    prospect_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Supprime un document transmis par erreur (mauvais fichier) avant
    conversion — le conseiller peut alors renvoyer le lien de collecte."""
    document = await db.get(DocumentProspect, document_id)
    if document is None or document.prospect_id != prospect_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document introuvable.")

    try:
        supprimer_document(document.cle_stockage)
    except StorageError:
        logger.warning("Suppression S3 échouée pour le document %s (prospect %s)", document_id, prospect_id)

    await audit_engine.enregistrer_action(
        db, entite_type="prospect", entite_id=prospect_id,
        action="Document supprimé", details=document.type_document or document.nom_fichier,
        auteur=user.nom_complet,
    )
    await db.delete(document)
    await db.commit()


@router.get("/{prospect_id}/historique", response_model=list[HistoriqueActionOut])
async def historique_prospect(prospect_id: int, db: AsyncSession = Depends(get_db)):
    return await audit_engine.lire_historique(db, "prospect", prospect_id)


@router.post("/{prospect_id}/envoyer-lien-documents", response_model=dict)
async def envoyer_lien_documents_prospect(
    prospect_id: int,
    payload: EnvoiLienClient,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Génère le lien de collecte documents (comme /token-documents) et l'envoie
    immédiatement au prospect par le canal choisi par le conseiller (SMS ou
    email) — automatise l'étape manuelle « copier le lien puis le transmettre »."""
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")

    token = await token_engine.generer_token_prospect_documents(db, prospect_id, cree_par=user.username)
    url = token_engine.construire_url_client(token.token, base_url=settings.portail_client_base_url)
    prenom = prospect.prenom or ""

    sms_envoye = False
    email_envoye = False
    if payload.canal == "sms":
        message_sms = (
            f"Bonjour {prenom}, voici votre lien personnel pour nous transmettre votre facture "
            f"et/ou votre test de débit : {url} (valable 14 jours). Votre conseiller."
        ).strip()
        sms_envoye = notification_engine.envoyer_sms(prospect.telephone or "", message_sms)
    else:
        corps_email = (
            f"<p>Bonjour {prenom},</p>"
            f"<p>Voici votre lien personnel pour nous transmettre votre facture et/ou votre test de débit :</p>"
            f'<p><a href="{url}">{url}</a></p>'
            f"<p>Ce lien est valable 14 jours.</p>"
            f"<p>Votre conseiller.</p>"
        )
        email_envoye = notification_engine.envoyer_email(
            prospect.email or "", "Votre lien personnel — transmission de documents", corps_email
        )

    return {
        "token": token.token,
        "url": url,
        "expire_le": token.date_expiration,
        "sms_envoye": sms_envoye,
        "email_envoye": email_envoye,
    }


@router.post("", response_model=ProspectOut, status_code=status.HTTP_201_CREATED)
async def creer_prospect(
    payload: ProspectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    donnees = payload.model_dump()
    donnees["ref"] = await reference_engine.generer_ref_prospect(db)
    prospect = Prospect(
        **donnees,
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
        cree_par=user.nom_complet,
    )
    db.add(prospect)
    await db.flush()
    await audit_engine.enregistrer_action(
        db, entite_type="prospect", entite_id=prospect.id,
        action="Prospect créé", auteur=user.nom_complet,
    )
    await db.commit()
    await db.refresh(prospect)
    return prospect


@router.put("/{prospect_id}", response_model=ProspectOut)
async def maj_prospect(prospect_id: int, payload: ProspectUpdate, db: AsyncSession = Depends(get_db)):
    """`ref` est immuable une fois le prospect créé (numéro de dossier interne,
    ne doit plus bouger) — silencieusement ignoré s'il est présent dans le
    payload, plutôt que de rejeter toute la requête."""
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        if champ == "ref":
            continue
        setattr(prospect, champ, valeur)
    await db.commit()
    await db.refresh(prospect)
    return prospect


@router.post("/{prospect_id}/relance-effectuee", response_model=ProspectOut)
async def relance_effectuee(
    prospect_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Marque une relance comme faite aujourd'hui : journalise l'action (source
    du `dernier_contact` calculé, voir prospect_scoring.dernier_contact) et
    programme la prochaine relance à +7 jours."""
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")

    await audit_engine.enregistrer_action(
        db, entite_type="prospect", entite_id=prospect_id,
        action="Relance effectuée", auteur=user.nom_complet,
    )
    prospect.date_relance = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    await db.commit()
    await db.refresh(prospect)

    dernier_contact = await prospect_scoring.dernier_contact(db, prospect_id)
    prospect.score = prospect_scoring.calculer_score(prospect, dernier_contact)
    prospect.dernier_contact = prospect_scoring.dernier_contact_affiche(prospect, dernier_contact)
    return prospect


@router.post("/{prospect_id}/contacter-telephone", response_model=ProspectOut)
async def contacter_telephone(
    prospect_id: int,
    payload: ContacterTelephoneIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Journalise un appel téléphonique passé au prospect et programme la
    prochaine relance à +7 jours (même logique que /relance-effectuee).
    Si le prospect n'a pas répondu, un SMS et/ou un email lui est envoyé pour
    l'informer que nous avons essayé de le joindre."""
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")

    action = "Appel téléphonique (répondu)" if payload.repondu else "Appel téléphonique (sans réponse)"
    await audit_engine.enregistrer_action(
        db, entite_type="prospect", entite_id=prospect_id, action=action, auteur=user.nom_complet,
    )
    prospect.date_relance = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    await db.commit()
    await db.refresh(prospect)

    if not payload.repondu:
        prenom = prospect.prenom or ""
        message = (
            f"Bonjour {prenom}, nous avons essayé de vous joindre par téléphone concernant "
            f"votre demande. Nous vous rappellerons prochainement. Votre conseiller IA Conseil."
        )
        if prospect.telephone:
            notification_engine.envoyer_sms(prospect.telephone, message)
        if prospect.email:
            notification_engine.envoyer_email(
                prospect.email,
                "Nous avons essayé de vous joindre",
                f"<p>Bonjour {prenom},</p><p>{message}</p>",
            )

    dernier_contact = await prospect_scoring.dernier_contact(db, prospect_id)
    prospect.score = prospect_scoring.calculer_score(prospect, dernier_contact)
    prospect.dernier_contact = prospect_scoring.dernier_contact_affiche(prospect, dernier_contact)
    return prospect


@router.delete("/{prospect_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_prospect(prospect_id: int, db: AsyncSession = Depends(get_db)):
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")
    await db.delete(prospect)
    await db.commit()
