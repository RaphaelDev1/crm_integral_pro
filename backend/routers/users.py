# ==============================================================================
#  UTILISATEURS — CRUD des comptes conseillers/admins. Réservé au rôle Admin.
#  Le hachage du mot de passe réutilise backend/core/security.py (PBKDF2-SHA256,
#  identique au flux /auth). La désactivation d'un compte passe par PUT
#  (`actif=False`) plutôt qu'un DELETE : on ne supprime jamais un utilisateur
#  ayant potentiellement des actions journalisées (cree_par, conseiller_responsable…).
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import hash_password, require_role
from backend.models.user import User
from backend.schemas.user import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_role("Admin"))])


@router.get("", response_model=list[UserOut])
async def lister_utilisateurs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.username))
    return result.scalars().all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def creer_utilisateur(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    identifiant = payload.username.strip().lower()
    existant = await db.execute(select(User).where(User.username == identifiant))
    if existant.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce nom d'utilisateur existe déjà.")

    utilisateur = User(
        username=identifiant,
        nom_complet=payload.nom_complet,
        password_hash=hash_password(payload.password),
        role=payload.role,
        telephone=payload.telephone,
        actif=True,
        doit_changer_mdp=True,
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )
    db.add(utilisateur)
    await db.commit()
    await db.refresh(utilisateur)
    return utilisateur


@router.put("/{user_id}", response_model=UserOut)
async def maj_utilisateur(user_id: int, payload: UserUpdate, db: AsyncSession = Depends(get_db)):
    utilisateur = await db.get(User, user_id)
    if utilisateur is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.")

    donnees = payload.model_dump(exclude_unset=True, exclude={"password"})
    for champ, valeur in donnees.items():
        setattr(utilisateur, champ, valeur)
    if payload.password:
        utilisateur.password_hash = hash_password(payload.password)
        utilisateur.doit_changer_mdp = True

    await db.commit()
    await db.refresh(utilisateur)
    return utilisateur
