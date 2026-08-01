# ==============================================================================
#  PARAMETRES — réglages clé/valeur (nom société, SMTP, Telegram, clé API...).
#  Réservé au rôle Admin : certaines valeurs sont des secrets en clair (voir
#  backend/models/parametre.py) et ne doivent pas être lisibles par tous les
#  conseillers.
# ==============================================================================
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import require_role
from backend.models.parametre import Parametre
from backend.schemas.parametre import ParametreOut, ParametreUpdate
from backend.services import storage_engine

router = APIRouter(prefix="/parametres", tags=["parametres"], dependencies=[Depends(require_role("Admin"))])

MIME_AUTORISES_LOGO = {"image/jpeg", "image/png", "image/webp"}
CLE_PARAMETRE_LOGO = "pdf_logo_cle_stockage"


@router.get("", response_model=list[ParametreOut])
async def lister_parametres(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Parametre).order_by(Parametre.cle))
    return result.scalars().all()


@router.put("/{cle}", response_model=ParametreOut)
async def maj_parametre(cle: str, payload: ParametreUpdate, db: AsyncSession = Depends(get_db)):
    parametre = await db.get(Parametre, cle)
    if parametre is None:
        parametre = Parametre(cle=cle, valeur=payload.valeur)
        db.add(parametre)
    else:
        parametre.valeur = payload.valeur
    await db.commit()
    await db.refresh(parametre)
    return parametre


@router.post("/logo", response_model=ParametreOut)
async def uploader_logo(fichier: UploadFile, db: AsyncSession = Depends(get_db)):
    """Upload du logo utilisé dans l'habillage du PDF de restitution (voir
    backend/services/restitution_pdf_engine.py) — enregistre sa clé de
    stockage dans le paramètre `pdf_logo_cle_stockage`."""
    contenu = await fichier.read()
    if not contenu:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Fichier vide.")
    if len(contenu) > 5 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Fichier trop volumineux (max 5 Mo).")

    mime_reel = storage_engine.deviner_mime_reel(contenu)
    if mime_reel not in MIME_AUTORISES_LOGO:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Type de fichier non autorisé (JPG, PNG ou WEBP uniquement, quelle que soit l'extension).",
        )

    try:
        cle = storage_engine.upload_fichier(
            prefixe="branding", type_document="logo", contenu=contenu, nom_fichier=fichier.filename or "logo.png",
        )
    except storage_engine.StorageError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Stockage impossible : {exc}")

    parametre = await db.get(Parametre, CLE_PARAMETRE_LOGO)
    if parametre is None:
        parametre = Parametre(cle=CLE_PARAMETRE_LOGO, valeur=cle)
        db.add(parametre)
    else:
        parametre.valeur = cle
    await db.commit()
    await db.refresh(parametre)
    return parametre
