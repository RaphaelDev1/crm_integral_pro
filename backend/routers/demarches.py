# ==============================================================================
#  DEMARCHES — génération et envoi tracé (LRE) des documents de démarche
#  post-vente (résiliation, portabilité, changement de fournisseur, mandat,
#  souscription) rattachés à un dossier. Protégé par JWT (conseillers).
#
#  Génération et envoi sont dispatchés en tâche Celery (comme KYC/signature) :
#  jamais de rendu PDF ni d'appel LRE synchrone dans le cycle requête/réponse.
# ==============================================================================
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.demarche import TYPES_DEMARCHE, Demarche
from backend.models.dossier import Dossier
from backend.schemas.demarche import (
    ChampsDemarcheUpdate,
    DemarcheCreate,
    DemarcheOut,
    DemarcheRequiseOut,
    DemarchesDossierOut,
    DocumentDemarcheUrlOut,
)
from backend.services import demarches_engine, storage_engine

router = APIRouter(tags=["demarches"], dependencies=[Depends(get_current_user)])


@router.get("/dossiers/{dossier_id}/demarches", response_model=DemarchesDossierOut)
async def lister_demarches(dossier_id: int, db: AsyncSession = Depends(get_db)):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")

    existantes = await demarches_engine.demarches_pour_dossier(db, dossier_id)
    types_existants = {d.type_demarche for d in existantes}
    requises_non_creees = [
        DemarcheRequiseOut(type_demarche=t, label=demarches_engine.LABELS_TYPE_DEMARCHE.get(t, t))
        for t in demarches_engine.demarches_requises(dossier)
        if t not in types_existants
    ]
    return DemarchesDossierOut(existantes=existantes, requises_non_creees=requises_non_creees)


@router.post("/dossiers/{dossier_id}/demarches", response_model=DemarcheOut, status_code=status.HTTP_201_CREATED)
async def creer_demarche(dossier_id: int, payload: DemarcheCreate, db: AsyncSession = Depends(get_db)):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    if payload.type_demarche not in TYPES_DEMARCHE:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Type de démarche inconnu : {payload.type_demarche}")
    return await demarches_engine.creer_demarche(db, dossier, payload.type_demarche)


@router.get("/demarches/{demarche_id}", response_model=DemarcheOut)
async def obtenir_demarche(demarche_id: int, db: AsyncSession = Depends(get_db)):
    demarche = await db.get(Demarche, demarche_id)
    if demarche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Démarche introuvable.")
    return demarche


@router.post("/demarches/{demarche_id}/generer", response_model=DemarcheOut, status_code=status.HTTP_202_ACCEPTED)
async def generer_demarche(demarche_id: int, db: AsyncSession = Depends(get_db)):
    from backend.workers.tasks import generer_document_demarche

    demarche = await db.get(Demarche, demarche_id)
    if demarche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Démarche introuvable.")
    try:
        generer_document_demarche.delay(demarche_id)
    except Exception as exc:  # noqa: BLE001 — broker Redis/Celery indisponible
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"Génération indisponible pour le moment : {exc}"
        ) from exc
    return demarche


@router.post("/demarches/{demarche_id}/envoyer", response_model=DemarcheOut, status_code=status.HTTP_202_ACCEPTED)
async def envoyer_demarche(demarche_id: int, db: AsyncSession = Depends(get_db)):
    from backend.workers.tasks import envoyer_demarche_lre

    demarche = await db.get(Demarche, demarche_id)
    if demarche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Démarche introuvable.")
    if demarche.statut != "generee":
        raise HTTPException(status.HTTP_409_CONFLICT, "Le document doit être généré avant d'être envoyé.")
    try:
        envoyer_demarche_lre.delay(demarche_id)
    except Exception as exc:  # noqa: BLE001 — broker Redis/Celery indisponible
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"Envoi indisponible pour le moment : {exc}"
        ) from exc
    return demarche


@router.patch("/demarches/{demarche_id}/champs", response_model=DemarcheOut)
async def renseigner_champs_demarche(
    demarche_id: int, payload: ChampsDemarcheUpdate, db: AsyncSession = Depends(get_db)
):
    demarche = await db.get(Demarche, demarche_id)
    if demarche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Démarche introuvable.")
    return await demarches_engine.marquer_champs(db, demarche, payload.valeurs)


@router.get("/demarches/{demarche_id}/document", response_model=DocumentDemarcheUrlOut)
async def obtenir_document_demarche(demarche_id: int, db: AsyncSession = Depends(get_db)):
    demarche = await db.get(Demarche, demarche_id)
    if demarche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Démarche introuvable.")
    if not demarche.document_url:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document pas encore généré.")
    try:
        url = storage_engine.url_signee(demarche.document_url)
    except storage_engine.StorageError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Stockage impossible : {exc}")
    return DocumentDemarcheUrlOut(url=url)
