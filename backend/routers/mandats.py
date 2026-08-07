# ==============================================================================
#  MANDATS — mandat de représentation (signature Yousign) rattaché au client
#  d'un dossier. Distinct de `mandat_honoraires` (rémunération du cabinet).
#  Deux façons de le faire signer :
#    - POST /dossiers/{id}/mandat : vrai circuit Yousign (asynchrone, Celery).
#    - POST /mandats/{id}/marquer-signe : fallback manuel, tant que la clé API
#      Yousign n'est pas configurée (backend/core/config.py::yousign_api_key).
#  Les deux convergent vers mandat_engine.traiter_mandat_signe (avance le
#  dossier, finalise la conversion prospect→client si besoin, programme une
#  relance de suivi).
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.dossier import Dossier
from backend.models.mandat import Mandat
from backend.models.user import User
from backend.schemas.mandat import MandatOut, MarquerMandatSigne
from backend.services import mandat_engine
from backend.services.storage_engine import StorageError, url_signee

router = APIRouter(prefix="/dossiers", tags=["mandats"], dependencies=[Depends(get_current_user)])
router_mandats = APIRouter(prefix="/mandats", tags=["mandats"], dependencies=[Depends(get_current_user)])


def _vers_mandat_out(mandat: Mandat) -> MandatOut:
    """Remplace la clé de stockage brute (`Mandat.pdf_url`) par une URL signée
    consultable depuis le navigateur — sans ça, le conseiller n'avait aucun
    moyen de vérifier que le PDF du mandat avait bien été généré après avoir
    cliqué « Envoyer pour signature »."""
    url = None
    if mandat.pdf_url:
        try:
            url = url_signee(mandat.pdf_url)
        except StorageError:
            url = None
    donnees = MandatOut.model_validate(mandat).model_dump()
    donnees["pdf_url"] = url
    return MandatOut(**donnees)


@router.get("/{dossier_id}/mandat", response_model=MandatOut | None)
async def obtenir_mandat(dossier_id: int, db: AsyncSession = Depends(get_db)):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    mandat = (
        await db.execute(
            select(Mandat).where(Mandat.client_id == dossier.client_id).order_by(Mandat.id.desc())
        )
    ).scalars().first()
    return _vers_mandat_out(mandat) if mandat else None


@router.post("/{dossier_id}/mandat", response_model=MandatOut, status_code=status.HTTP_201_CREATED)
async def envoyer_mandat(dossier_id: int, db: AsyncSession = Depends(get_db)):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    try:
        mandat = await mandat_engine.creer_et_envoyer_mandat(db, dossier)
        return _vers_mandat_out(mandat)
    except mandat_engine.MandatEngineError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router_mandats.post("/{mandat_id}/marquer-signe", response_model=MandatOut)
async def marquer_mandat_signe(
    mandat_id: int,
    payload: MarquerMandatSigne,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fallback manuel : marque le mandat signé sans passer par Yousign — tant
    que la clé API n'est pas configurée, ou pour rattraper une signature
    obtenue hors-ligne. Déclenche la même suite que le webhook Yousign
    (progression du dossier, conversion prospect→client, relance)."""
    mandat = await db.get(Mandat, mandat_id)
    if mandat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mandat introuvable.")
    if mandat.statut == "signe":
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce mandat est déjà marqué signé.")
    mandat.statut = "signe"
    mandat.date_signature = datetime.now().strftime("%d/%m/%Y %H:%M")
    mandat.notes = f"Signé manuellement (déclaré par {payload.signataire})."
    await mandat_engine.traiter_mandat_signe(db, mandat, par=user.nom_complet)
    await db.refresh(mandat)
    return _vers_mandat_out(mandat)
