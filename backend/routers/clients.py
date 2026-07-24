# ==============================================================================
#  CLIENTS — CRUD, protégé par JWT (get_current_user).
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.client import Client
from backend.models.dossier import Dossier
from backend.models.facture_analyse import FactureAnalyse
from backend.models.mandat import Mandat
from backend.models.mandat_honoraires import MandatHonoraires
from backend.models.user import User
from backend.schemas.briefing import ClientBriefingOut
from backend.schemas.client import ClientCreate, ClientOut, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ClientOut])
async def lister_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).order_by(Client.id.desc()))
    return result.scalars().all()


@router.get("/{client_id}/briefing", response_model=ClientBriefingOut)
async def briefing_client(client_id: int, db: AsyncSession = Depends(get_db)):
    """Vue agrégée à consulter avant d'appeler un client : ses informations,
    son dossier de souscription en cours et la dernière facture analysée —
    pour que le conseiller ait le maximum d'informations en un seul appel."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")

    result_d = await db.execute(
        select(Dossier).where(Dossier.client_id == client_id).order_by(Dossier.id.desc())
    )
    dossiers = result_d.scalars().all()
    dossier_en_cours = next(
        (d for d in dossiers if d.statut not in ("actif", "echec", "annule")), None
    ) or (dossiers[0] if dossiers else None)

    result_f = await db.execute(
        select(FactureAnalyse)
        .where(FactureAnalyse.client_id == client_id)
        .order_by(FactureAnalyse.id.desc())
        .limit(1)
    )
    derniere_facture = result_f.scalar_one_or_none()

    mandat_representation = (
        await db.execute(
            select(Mandat).where(Mandat.client_id == client_id).order_by(Mandat.id.desc()).limit(1)
        )
    ).scalar_one_or_none()

    mandat_honoraires = None
    if dossier_en_cours is not None:
        mandat_honoraires = (
            await db.execute(
                select(MandatHonoraires).where(MandatHonoraires.dossier_id == dossier_en_cours.id)
            )
        ).scalar_one_or_none()

    return ClientBriefingOut(
        client=client,
        dossier_en_cours=dossier_en_cours,
        derniere_facture=derniere_facture,
        nb_dossiers=len(dossiers),
        mandat_representation=mandat_representation,
        mandat_honoraires=mandat_honoraires,
    )


@router.get("/{client_id}", response_model=ClientOut)
async def obtenir_client(client_id: int, db: AsyncSession = Depends(get_db)):
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    return client


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
async def creer_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    client = Client(
        **payload.model_dump(),
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
        cree_par=user.nom_complet,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client


@router.put("/{client_id}", response_model=ClientOut)
async def maj_client(client_id: int, payload: ClientUpdate, db: AsyncSession = Depends(get_db)):
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(client, champ, valeur)
    await db.commit()
    await db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_client(client_id: int, db: AsyncSession = Depends(get_db)):
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    await db.delete(client)
    await db.commit()
