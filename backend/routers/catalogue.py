# ==============================================================================
#  CATALOGUE — pipeline de découverte d'offres (sources à ingérer + offres
#  détectées en attente de validation). Le relevé automatique est déclenché
#  par la tâche Celery Beat périodique
#  (backend/workers/tasks.py::ingerer_catalogue_periodique) ;
#  `/catalogue/sources/{id}/ingerer` permet un déclenchement manuel immédiat
#  depuis l'admin. Réservé au rôle Admin : le catalogue pilote les offres
#  proposées aux clients.
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import require_role
from backend.models.catalogue_source import CatalogueSource
from backend.models.offre_staging import OffreStaging
from backend.schemas.catalogue import (
    CatalogueSourceCreate,
    CatalogueSourceOut,
    CatalogueSourceUpdate,
    IngestionResumeOut,
    OffreStagingOut,
)
from backend.services import catalogue_engine

router = APIRouter(prefix="/catalogue", tags=["catalogue"], dependencies=[Depends(require_role("Admin"))])


@router.get("/sources", response_model=list[CatalogueSourceOut])
async def lister_sources(actif_seulement: bool = False, db: AsyncSession = Depends(get_db)):
    requete = select(CatalogueSource).order_by(CatalogueSource.univers, CatalogueSource.categorie, CatalogueSource.fournisseur)
    if actif_seulement:
        requete = requete.where(CatalogueSource.actif.is_(True))
    result = await db.execute(requete)
    return result.scalars().all()


@router.post("/sources", response_model=CatalogueSourceOut, status_code=status.HTTP_201_CREATED)
async def creer_source(payload: CatalogueSourceCreate, db: AsyncSession = Depends(get_db)):
    source = CatalogueSource(
        **payload.model_dump(),
        robots_ok=catalogue_engine.verifier_robots(payload.url),
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.put("/sources/{source_id}", response_model=CatalogueSourceOut)
async def maj_source(source_id: int, payload: CatalogueSourceUpdate, db: AsyncSession = Depends(get_db)):
    source = await db.get(CatalogueSource, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source introuvable.")
    donnees = payload.model_dump(exclude_unset=True)
    if "url" in donnees:
        donnees["robots_ok"] = catalogue_engine.verifier_robots(donnees["url"])
    for champ, valeur in donnees.items():
        setattr(source, champ, valeur)
    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_source(source_id: int, db: AsyncSession = Depends(get_db)):
    source = await db.get(CatalogueSource, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source introuvable.")
    await db.delete(source)
    await db.commit()


@router.post("/sources/{source_id}/ingerer", response_model=IngestionResumeOut)
async def ingerer_source_manuellement(source_id: int, db: AsyncSession = Depends(get_db)):
    """Déclenchement manuel immédiat (hors planification Celery Beat) — utile
    pour tester une source fraîchement ajoutée sans attendre le prochain
    passage nocturne."""
    source = await db.get(CatalogueSource, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source introuvable.")
    return await catalogue_engine.ingerer_source(db, source_id)


@router.get("/offres-staging", response_model=list[OffreStagingOut])
async def lister_offres_staging(statut: str = "en_attente", db: AsyncSession = Depends(get_db)):
    requete = select(OffreStaging).order_by(OffreStaging.id.desc())
    if statut:
        requete = requete.where(OffreStaging.statut == statut)
    result = await db.execute(requete)
    return result.scalars().all()


@router.post("/offres-staging/{staging_id}/valider", response_model=dict)
async def valider_offre(staging_id: int, db: AsyncSession = Depends(get_db)):
    ok, message = await catalogue_engine.valider_offre_staging(db, staging_id)
    if not ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)
    return {"ok": True, "message": message}


@router.post("/offres-staging/{staging_id}/rejeter", response_model=dict)
async def rejeter_offre(staging_id: int, db: AsyncSession = Depends(get_db)):
    ok = await catalogue_engine.rejeter_offre_staging(db, staging_id)
    if not ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Offre introuvable ou déjà traitée.")
    return {"ok": True}
