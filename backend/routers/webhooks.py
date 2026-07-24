# ==============================================================================
#  WEBHOOKS — endpoints appelés par des prestataires externes (Yousign). Non
#  protégés par JWT : l'authenticité est vérifiée via signature HMAC.
# ==============================================================================
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.models.mandat import Mandat
from backend.services import signature_engine
from backend.workers.tasks import telecharger_mandat_signe

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/yousign", status_code=status.HTTP_204_NO_CONTENT)
async def webhook_yousign(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_yousign_signature_256: str | None = Header(default=None),
):
    corps_brut = await request.body()
    if not signature_engine.verifier_signature_webhook(corps_brut, x_yousign_signature_256):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Signature webhook invalide.")

    evenement = signature_engine.parser_evenement_webhook(await request.json())
    signature_request_id = evenement["signature_request_id"]
    if not signature_request_id:
        return

    mandat = (
        await db.execute(select(Mandat).where(Mandat.yousign_signature_request_id == signature_request_id))
    ).scalar_one_or_none()
    if mandat is None:
        return

    if evenement["event_name"] == "signature_request.done":
        telecharger_mandat_signe.delay(mandat.id)
    elif evenement["event_name"] == "signature_request.refused":
        mandat.statut = "refuse"
        await db.commit()
