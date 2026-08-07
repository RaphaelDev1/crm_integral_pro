# ==============================================================================
#  HONORAIRES — mandat de rémunération du cabinet, rattaché à un dossier.
#  Distinct de `routers/factures.py` (analyse LLM des factures opérateur du
#  client) et de `mandats` (signature Yousign du mandat de représentation).
#  Protégé par JWT (conseillers uniquement).
# ==============================================================================
import base64
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.client import Client
from backend.models.dossier import Dossier
from backend.models.mandat_honoraires import MandatHonoraires
from backend.models.parametre import Parametre
from backend.schemas.mandat_honoraires import (
    EnvoiMandatHonoraires,
    EnvoiMandatHonorairesResultat,
    MandatHonorairesCreate,
    MandatHonorairesOut,
    MarquerSigneHonoraires,
)
from backend.services import document_engine, notification_engine

router = APIRouter(prefix="/dossiers", tags=["honoraires"], dependencies=[Depends(get_current_user)])

# Prefix distinct de /dossiers exprès : évite toute collision d'ordre de route
# avec GET /dossiers/{dossier_id} (voir routers/dossiers.py) pour lister tous
# les mandats d'honoraires (aucune vue globale n'existait jusqu'ici, seulement
# un mandat par dossier).
router_liste = APIRouter(prefix="/honoraires", tags=["honoraires"], dependencies=[Depends(get_current_user)])

# Réglable par l'admin via GET/PUT /parametres/{cle} (panneau admin > Paramètres
# > Réglages) sans redéploiement. Route exposée ici (pas sous /parametres, qui
# est réservé au rôle Admin car il expose aussi des secrets) pour que
# n'importe quel conseiller puisse pré-remplir le taux par défaut.
CLE_TAUX_HONORAIRES_DEFAUT = "taux_honoraires_defaut"
TAUX_HONORAIRES_DEFAUT_INITIAL = 20.0


@router_liste.get("", response_model=list[MandatHonorairesOut])
async def lister_mandats_honoraires(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MandatHonoraires).order_by(MandatHonoraires.id.desc()))
    return result.scalars().all()


@router_liste.get("/taux-defaut", response_model=dict)
async def obtenir_taux_honoraires_defaut(db: AsyncSession = Depends(get_db)):
    parametre = await db.get(Parametre, CLE_TAUX_HONORAIRES_DEFAUT)
    if parametre is None or parametre.valeur is None:
        return {"taux": TAUX_HONORAIRES_DEFAUT_INITIAL}
    try:
        return {"taux": float(parametre.valeur)}
    except ValueError:
        return {"taux": TAUX_HONORAIRES_DEFAUT_INITIAL}


@router.get("/{dossier_id}/mandat-honoraires", response_model=MandatHonorairesOut | None)
async def obtenir_mandat_honoraires(dossier_id: int, db: AsyncSession = Depends(get_db)):
    return (
        await db.execute(select(MandatHonoraires).where(MandatHonoraires.dossier_id == dossier_id))
    ).scalar_one_or_none()


@router.post("/{dossier_id}/mandat-honoraires", response_model=MandatHonorairesOut, status_code=status.HTTP_201_CREATED)
async def creer_mandat_honoraires(
    dossier_id: int, payload: MandatHonorairesCreate, db: AsyncSession = Depends(get_db)
):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    existant = (
        await db.execute(select(MandatHonoraires).where(MandatHonoraires.dossier_id == dossier_id))
    ).scalar_one_or_none()
    if existant is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Un mandat d'honoraires existe déjà pour ce dossier.")
    mandat = MandatHonoraires(
        dossier_id=dossier_id,
        montant=payload.montant,
        taux=payload.taux,
        statut="envoye",
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )
    db.add(mandat)
    await db.commit()
    await db.refresh(mandat)
    return mandat


@router.post("/{dossier_id}/mandat-honoraires/marquer-signe", response_model=MandatHonorairesOut)
async def marquer_signe_honoraires(
    dossier_id: int, payload: MarquerSigneHonoraires, db: AsyncSession = Depends(get_db)
):
    mandat = (
        await db.execute(select(MandatHonoraires).where(MandatHonoraires.dossier_id == dossier_id))
    ).scalar_one_or_none()
    if mandat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun mandat d'honoraires pour ce dossier.")
    mandat.statut = "signe"
    mandat.signataire = payload.signataire
    mandat.date_signature = datetime.now().strftime("%d/%m/%Y %H:%M")
    await db.commit()
    await db.refresh(mandat)
    return mandat


async def _charger_pour_pdf(dossier_id: int, db: AsyncSession) -> tuple[Dossier, Client, MandatHonoraires]:
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    mandat = (
        await db.execute(select(MandatHonoraires).where(MandatHonoraires.dossier_id == dossier_id))
    ).scalar_one_or_none()
    if mandat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun mandat d'honoraires pour ce dossier.")
    client = await db.get(Client, dossier.client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    return dossier, client, mandat


@router.get("/{dossier_id}/mandat-honoraires/pdf")
async def telecharger_mandat_honoraires(dossier_id: int, db: AsyncSession = Depends(get_db)):
    """Génère à la volée le PDF du mandat d'honoraires (pas de stockage S3,
    comme /pdf-restitution — reste rapide, pas de dépendance Celery)."""
    dossier, client, mandat = await _charger_pour_pdf(dossier_id, db)
    pdf_bytes = document_engine.generer_pdf_mandat_honoraires(dossier, client, mandat)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="mandat_honoraires_dossier_{dossier_id}.pdf"'},
    )


@router.post("/{dossier_id}/mandat-honoraires/envoyer", response_model=EnvoiMandatHonorairesResultat)
async def envoyer_mandat_honoraires(
    dossier_id: int, payload: EnvoiMandatHonoraires, db: AsyncSession = Depends(get_db)
):
    """Envoie le mandat d'honoraires au client par email (PDF en pièce
    jointe) ou par SMS (notification texte — pas de pièce jointe possible par
    ce canal)."""
    dossier, client, mandat = await _charger_pour_pdf(dossier_id, db)
    prenom = client.prenom or ""

    if payload.canal == "sms":
        message = (
            f"Bonjour {prenom}, votre mandat d'honoraires ({mandat.montant:.2f} EUR) est pret — "
            f"votre conseiller vous le transmettra pour signature. Votre conseiller."
        ).strip()
        sms_envoye = notification_engine.envoyer_sms(client.telephone or "", message)
        return EnvoiMandatHonorairesResultat(sms_envoye=sms_envoye)

    pdf_bytes = document_engine.generer_pdf_mandat_honoraires(dossier, client, mandat)
    corps_html = (
        f"<p>Bonjour {prenom},</p>"
        "<p>Veuillez trouver ci-joint votre mandat d'honoraires.</p>"
        "<p>Votre conseiller.</p>"
    )
    email_envoye = notification_engine.envoyer_email(
        client.email or "",
        "Votre mandat d'honoraires",
        corps_html,
        attachments=[{
            "filename": f"mandat_honoraires_dossier_{dossier_id}.pdf",
            "content": base64.b64encode(pdf_bytes).decode("ascii"),
        }],
    )
    return EnvoiMandatHonorairesResultat(email_envoye=email_envoye)
