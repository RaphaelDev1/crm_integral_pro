# ==============================================================================
#  AGENT D'AUDIT — boucle agentique Claude tool-use (backend/services/audit_agent.py).
#  Ouvert à tout conseiller authentifié (pas Admin-only) : c'est un outil de
#  travail quotidien, invoqué depuis l'étape 4 du wizard Diagnostic.
# ==============================================================================
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.schemas.audit import AuditRequest, AuditResultOut
from backend.services import audit_agent

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(get_current_user)])


@router.post("/lancer", response_model=AuditResultOut)
async def lancer_audit(payload: AuditRequest, db: AsyncSession = Depends(get_db)):
    return await audit_agent.lancer_audit(
        db,
        payload.situation.model_dump(),
        contrats=[c.model_dump() for c in payload.contrats],
    )
