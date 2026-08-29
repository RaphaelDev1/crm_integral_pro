# ==============================================================================
#  FACTURES — analyse structurée d'une facture PDF (télécom/énergie) via LLM.
#  Expose backend/services/facture_analyzer.py en HTTP (jusque-là écrit mais
#  jamais appelable autrement qu'en import Python direct).
#
#  Si `client_id` est fourni, le résultat est aussi persisté (table
#  `factures_analysees`) pour alimenter le briefing conseiller avant appel
#  (GET /clients/{id}/briefing) — sans ce champ, l'analyse reste ponctuelle
#  (comportement d'origine, ex. wizard de diagnostic à la création).
# ==============================================================================
import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.client import Client
from backend.models.facture_analyse import FactureAnalyse
from backend.models.prospect import Prospect
from backend.models.user import User
from backend.schemas.facture import FactureAnalyseOut
from backend.services.facture_analyzer import FactureAnalyzerError, analyser_facture

router = APIRouter(prefix="/factures", tags=["factures"], dependencies=[Depends(get_current_user)])


@router.post("/analyze", response_model=FactureAnalyseOut)
async def analyser(
    fichier: UploadFile,
    client_id: int | None = Form(None),
    prospect_id: int | None = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if Path(fichier.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Seuls les fichiers PDF sont acceptés.")

    if client_id is not None and await db.get(Client, client_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    if prospect_id is not None and await db.get(Prospect, prospect_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect introuvable.")

    contenu = await fichier.read()
    # delete=False + suppression manuelle : sous Windows, un NamedTemporaryFile
    # ouvert (delete=True) ne peut pas être rouvert par chemin par un second
    # appel (PermissionError) — analyser_facture() a besoin de le rouvrir.
    fd, chemin_tmp = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(contenu)
        resultat = analyser_facture(chemin_tmp)
    except FactureAnalyzerError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    finally:
        os.unlink(chemin_tmp)

    if client_id is not None or prospect_id is not None:
        db.add(FactureAnalyse(
            client_id=client_id,
            prospect_id=prospect_id,
            **resultat,
            date_analyse=datetime.now().strftime("%d/%m/%Y %H:%M"),
            analyse_par=user.username,
        ))
        await db.commit()

    return resultat
