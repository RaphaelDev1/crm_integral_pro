# ==============================================================================
#  ADMIN — actions d'administration transverses, réservées au rôle Admin.
# ==============================================================================
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import require_role
from backend.schemas.admin import PurgeDonneesTestOut
from backend.services.purge_test_data import PurgeInterdite, purger_prospects_et_clients

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("Admin"))])


@router.delete("/donnees-test", response_model=PurgeDonneesTestOut)
async def purger_donnees_test(db: AsyncSession = Depends(get_db)):
    """Supprime TOUS les prospects et clients (et leurs dépendances : dossiers,
    mandats, documents, factures...), fichiers de stockage inclus — outil de
    dev/test pour désencombrer la base, voir purge_test_data.py. Irréversible,
    bloqué en production."""
    try:
        return await purger_prospects_et_clients(db)
    except PurgeInterdite as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
