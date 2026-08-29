# ==============================================================================
#  CLIENTS (IA Conseil) — CRUD minimal sur la table `client` neuve (distincte
#  de `clients`, le CRM historique — voir backend/models/ia_conseil.py).
# ==============================================================================
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.ia_conseil import ClientConseil
from backend.models.user import User
from backend.schemas.ia_conseil import ClientConseilCreate, ClientConseilOut, CrossSellSuggestion, ScoreClientOut
from backend.services import churn_engine, cross_sell_engine

router = APIRouter(prefix="/api/v1/clients", tags=["ia_conseil_clients"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ClientConseilOut])
async def lister_clients(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(ClientConseil).order_by(ClientConseil.cree_le.desc())
    if user.role != "Admin":
        query = query.where((ClientConseil.conseiller_id == user.id) | (ClientConseil.conseiller_id.is_(None)))
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{client_id}", response_model=ClientConseilOut)
async def obtenir_client(client_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    client = await db.get(ClientConseil, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    if user.role != "Admin" and client.conseiller_id is not None and client.conseiller_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette fiche appartient à un autre conseiller.")
    return client


@router.get("/{client_id}/cross-sell", response_model=list[CrossSellSuggestion])
async def cross_sell(client_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Suggestions inter-catégories (§2.4) hors contexte de trame — pour la
    fiche client, à partir des sessions et souscriptions déjà connues."""
    client = await db.get(ClientConseil, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    if user.role != "Admin" and client.conseiller_id is not None and client.conseiller_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette fiche appartient à un autre conseiller.")
    return await cross_sell_engine.suggestions_cross_sell(db, client_id)


@router.get("/{client_id}/scores", response_model=ScoreClientOut)
async def scores(client_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Prévision de churn + probabilité de cross-sell + segmentation (§3.5).
    `source` indique si proba_churn vient du modèle entraîné ou d'un repli
    heuristique (échantillon d'entraînement insuffisant, voir churn_engine.py)."""
    client = await db.get(ClientConseil, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    if user.role != "Admin" and client.conseiller_id is not None and client.conseiller_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette fiche appartient à un autre conseiller.")
    return await churn_engine.score_client(db, client_id)


@router.post("", response_model=ClientConseilOut, status_code=status.HTTP_201_CREATED)
async def creer_client(
    payload: ClientConseilCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    client = ClientConseil(**payload.model_dump(), conseiller_id=user.id)
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client
