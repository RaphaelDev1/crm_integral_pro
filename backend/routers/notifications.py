# ==============================================================================
#  NOTIFICATIONS — alertes in-app du conseiller connecté (voir
#  backend/services/notification_engine.py::creer_notification_conseiller).
# ==============================================================================
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.notification import Notification
from backend.models.user import User
from backend.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[NotificationOut])
async def lister_notifications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Les miennes, non lues en premier puis les plus récentes."""
    requete = (
        select(Notification)
        .where(Notification.conseiller_username == user.username)
        .order_by(Notification.lu.asc(), Notification.id.desc())
    )
    result = await db.execute(requete)
    return result.scalars().all()


@router.post("/{notification_id}/lu", response_model=NotificationOut)
async def marquer_lu(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notification = await db.get(Notification, notification_id)
    if notification is None or notification.conseiller_username != user.username:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification introuvable.")
    notification.lu = True
    await db.commit()
    await db.refresh(notification)
    return notification
