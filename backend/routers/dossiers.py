# ==============================================================================
#  DOSSIERS — CRUD + machine à états. Protégé par JWT (conseillers uniquement).
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.dossier import Dossier
from backend.models.user import User
from backend.schemas.dossier import (
    DossierCreate,
    DossierOut,
    DossierUpdate,
    EnvoiLienClient,
    EtapeTimeline,
    NoteDossierCreate,
    TransitionStatut,
)
from backend.services import dossier_engine, dossier_notifications, token_engine

router = APIRouter(prefix="/dossiers", tags=["dossiers"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[DossierOut])
async def lister_dossiers(
    statut: str | None = None,
    client_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Dossier).order_by(Dossier.id.desc())
    if statut:
        query = query.where(Dossier.statut == statut)
    if client_id:
        query = query.where(Dossier.client_id == client_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{dossier_id}", response_model=DossierOut)
async def obtenir_dossier(dossier_id: int, db: AsyncSession = Depends(get_db)):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    return dossier


@router.post("", response_model=DossierOut, status_code=status.HTTP_201_CREATED)
async def creer_dossier(
    payload: DossierCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dossier = Dossier(
        **payload.model_dump(),
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
        conseiller_responsable=user.nom_complet,
        notes_workflow=[],
    )
    db.add(dossier)
    await db.commit()
    await db.refresh(dossier)
    return dossier


@router.put("/{dossier_id}", response_model=DossierOut)
async def maj_dossier(
    dossier_id: int, payload: DossierUpdate, db: AsyncSession = Depends(get_db)
):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(dossier, champ, valeur)
    await db.commit()
    await db.refresh(dossier)
    return dossier


@router.post("/{dossier_id}/transition", response_model=DossierOut)
async def transiter_dossier(
    dossier_id: int,
    payload: TransitionStatut,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.models.client import Client

    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    client = await db.get(Client, dossier.client_id)
    try:
        await dossier_engine.transiter(
            db, dossier, payload.nouveau_statut,
            par=user.username, commentaire=payload.commentaire,
            on_transition=lambda d, _ancien: dossier_notifications.notifier_transition(d, client),
        )
    except dossier_engine.TransitionInvalide as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    return dossier


@router.get("/{dossier_id}/timeline", response_model=list[EtapeTimeline])
async def obtenir_timeline_dossier(dossier_id: int, db: AsyncSession = Depends(get_db)):
    """Étapes du stepper à afficher au conseiller (même construction que celle
    servie au client via /portail/{token}/suivi)."""
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    return dossier_engine.construire_timeline(dossier)


@router.post("/{dossier_id}/notes", response_model=DossierOut)
async def ajouter_note_dossier(
    dossier_id: int,
    payload: NoteDossierCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ajoute une note manuelle au journal du dossier (compte-rendu d'appel,
    remarque) sans changer son statut."""
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    return await dossier_engine.ajouter_note(db, dossier, payload.texte, par=user.username)


@router.post("/{dossier_id}/token-client", response_model=dict)
async def generer_lien_client(
    dossier_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Génère un lien unique à envoyer au client (SMS/email) pour qu'il accède
    à son dossier sans se connecter.
    """
    from backend.core.config import settings

    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")

    token = await token_engine.generer_token(
        db,
        client_id=dossier.client_id,
        dossier_id=dossier.id,
        cree_par=user.username,
    )

    url = token_engine.construire_url_client(token.token, base_url=settings.portail_client_base_url)
    return {
        "token": token.token,
        "url": url,
        "expire_le": token.date_expiration,
        "message_sms_suggere": (
            f"Bonjour, voici votre lien personnel pour finaliser votre changement d'offre "
            f"en quelques clics : {url} (valable 30 jours). Votre conseiller."
        ),
    }


@router.post("/{dossier_id}/envoyer-lien-client", response_model=dict)
async def envoyer_lien_client(
    dossier_id: int,
    payload: EnvoiLienClient,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Génère un lien unique (comme /token-client) et l'envoie immédiatement au
    client par le canal choisi par le conseiller (SMS ou email, selon la
    préférence du client) — automatise l'étape manuelle « copier le lien puis
    le transmettre » du flux conseiller."""
    from backend.core.config import settings
    from backend.models.client import Client
    from backend.services import notification_engine

    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    client = await db.get(Client, dossier.client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")

    token = await token_engine.generer_token(
        db,
        client_id=dossier.client_id,
        dossier_id=dossier.id,
        cree_par=user.username,
    )
    url = token_engine.construire_url_client(token.token, base_url=settings.portail_client_base_url)
    prenom = client.prenom or ""

    sms_envoye = False
    email_envoye = False
    if payload.canal == "sms":
        message_sms = (
            f"Bonjour {prenom}, voici votre lien personnel pour finaliser votre changement d'offre "
            f"en quelques clics : {url} (valable 30 jours). Votre conseiller."
        ).strip()
        sms_envoye = notification_engine.envoyer_sms(client.telephone or "", message_sms)
    else:
        corps_email = (
            f"<p>Bonjour {prenom},</p>"
            f"<p>Voici votre lien personnel pour suivre et finaliser votre dossier en quelques clics :</p>"
            f'<p><a href="{url}">{url}</a></p>'
            f"<p>Ce lien est valable 30 jours.</p>"
            f"<p>Votre conseiller.</p>"
        )
        email_envoye = notification_engine.envoyer_email(
            client.email or "", "Votre lien personnel — suivi de dossier", corps_email
        )

    return {
        "token": token.token,
        "url": url,
        "expire_le": token.date_expiration,
        "sms_envoye": sms_envoye,
        "email_envoye": email_envoye,
    }
