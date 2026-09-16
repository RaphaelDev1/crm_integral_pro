# ==============================================================================
#  CONTRATS — CRUD, protégé par JWT. Rattachés à un client OU un prospect non
#  converti (fiche prospect/client, onglet Contrats) — un prospect a souvent
#  déjà des contrats en cours chez un concurrent avant de devenir client.
#  Chaque écriture est journalisée sur l'entité "client" ou "prospect"
#  (backend/services/audit_engine.py) pour apparaître dans son historique.
# ==============================================================================
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.client import Client
from backend.models.contrat import Contrat
from backend.models.prospect import Prospect
from backend.models.user import User
from backend.schemas.contrat import ContratCreate, ContratOut, ContratUpdate, EstimationContratOut
from backend.services import audit_engine, estimation_publique

router = APIRouter(prefix="/contrats", tags=["contrats"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ContratOut])
async def lister_contrats(
    client_id: int | None = None, prospect_id: int | None = None, db: AsyncSession = Depends(get_db)
):
    requete = select(Contrat).order_by(Contrat.id.desc())
    if client_id is not None:
        requete = requete.where(Contrat.client_id == client_id)
    if prospect_id is not None:
        requete = requete.where(Contrat.prospect_id == prospect_id)
    result = await db.execute(requete)
    return result.scalars().all()


@router.get("/estimation", response_model=EstimationContratOut)
async def estimer_contrats(
    client_id: int | None = None, prospect_id: int | None = None, db: AsyncSession = Depends(get_db)
):
    """Fourchette d'économie annuelle (basse/haute/typique), calculée avec le
    même moteur que la landing publique (backend/services/estimation_publique.py)
    à partir des contrats "Actuel" (situation avant nous) de l'entité."""
    if client_id is None and prospect_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "client_id ou prospect_id requis.")

    age: int | None = None
    tranche_age: str | None = None
    if client_id is not None:
        entite = await db.get(Client, client_id)
        age = entite.age if entite else None
        tranche_age = entite.tranche_age if entite else None
    else:
        entite = await db.get(Prospect, prospect_id)
        age = entite.age if entite else None
        tranche_age = entite.tranche_age if entite else None

    requete = select(Contrat.categorie, Contrat.cout_mensuel).where(Contrat.statut_contrat == "Actuel")
    requete = requete.where(Contrat.client_id == client_id) if client_id is not None else requete.where(
        Contrat.prospect_id == prospect_id
    )
    result = await db.execute(requete)
    depenses: dict[str, float] = {}
    for categorie, cout in result.all():
        if categorie:
            depenses[categorie] = depenses.get(categorie, 0) + (cout or 0)

    estimation = await estimation_publique.estimer(db, depenses, age=age, tranche=tranche_age)
    return EstimationContratOut(
        lignes=[
            {
                "categorie": l.categorie,
                "cout_actuel_mensuel": l.cout_actuel_mensuel,
                "notre_moyenne_mensuel": l.notre_moyenne_mensuel,
                "economie_mensuelle_basse": l.economie_mensuelle_basse,
                "economie_mensuelle_haute": l.economie_mensuelle_haute,
                "economie_annuelle_typique": l.economie_annuelle_typique,
                "source": l.source,
                "echantillon": l.echantillon,
                "tranche_age_utilisee": l.tranche_age_utilisee,
            }
            for l in estimation.lignes
        ],
        economie_annuelle_totale_basse=estimation.economie_annuelle_totale_basse,
        economie_annuelle_totale_haute=estimation.economie_annuelle_totale_haute,
        economie_annuelle_totale_typique=estimation.economie_annuelle_totale_typique,
        calculee_le=estimation.calculee_le or datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )


@router.get("/{contrat_id}", response_model=ContratOut)
async def obtenir_contrat(contrat_id: int, db: AsyncSession = Depends(get_db)):
    contrat = await db.get(Contrat, contrat_id)
    if contrat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrat introuvable.")
    return contrat


def _journaliser(contrat: Contrat) -> tuple[str, int | None]:
    if contrat.client_id is not None:
        return "client", contrat.client_id
    return "prospect", contrat.prospect_id


async def _autres_lignes_mobiles(
    db: AsyncSession, *, client_id: int | None, prospect_id: int | None, exclure_id: int | None = None
) -> list[Contrat]:
    requete = select(Contrat).where(Contrat.categorie == "Forfait mobile")
    requete = requete.where(Contrat.client_id == client_id) if client_id is not None else requete.where(
        Contrat.prospect_id == prospect_id
    )
    if exclure_id is not None:
        requete = requete.where(Contrat.id != exclure_id)
    return (await db.execute(requete)).scalars().all()


@router.post("", response_model=ContratOut, status_code=status.HTTP_201_CREATED)
async def creer_contrat(
    payload: ContratCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    donnees = payload.model_dump()
    if donnees.get("categorie") == "Forfait mobile":
        # Une seule ligne mobile = elle est d'office la "ligne principale",
        # sans action du conseiller — voir migration 0041.
        autres = await _autres_lignes_mobiles(
            db, client_id=payload.client_id, prospect_id=payload.prospect_id
        )
        donnees["ligne_principale"] = not autres
    contrat = Contrat(**donnees, cree_par=user.nom_complet)
    db.add(contrat)
    entite_type, entite_id = _journaliser(contrat)
    await audit_engine.enregistrer_action(
        db, entite_type=entite_type, entite_id=entite_id,
        action="Contrat ajouté", details=payload.fournisseur, auteur=user.nom_complet,
    )
    await db.commit()
    await db.refresh(contrat)
    return contrat


@router.put("/{contrat_id}", response_model=ContratOut)
async def maj_contrat(
    contrat_id: int,
    payload: ContratUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contrat = await db.get(Contrat, contrat_id)
    if contrat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrat introuvable.")
    valeurs = payload.model_dump(exclude_unset=True)
    for champ, valeur in valeurs.items():
        setattr(contrat, champ, valeur)
    if valeurs.get("ligne_principale") is True:
        # Une seule ligne mobile "principale" à la fois pour cette entité.
        autres = await _autres_lignes_mobiles(
            db, client_id=contrat.client_id, prospect_id=contrat.prospect_id, exclure_id=contrat.id
        )
        for autre in autres:
            autre.ligne_principale = False
    entite_type, entite_id = _journaliser(contrat)
    if entite_id is not None:
        await audit_engine.enregistrer_action(
            db, entite_type=entite_type, entite_id=entite_id,
            action="Contrat modifié", details=contrat.fournisseur, auteur=user.nom_complet,
        )
    await db.commit()
    await db.refresh(contrat)
    return contrat


@router.delete("/{contrat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_contrat(
    contrat_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contrat = await db.get(Contrat, contrat_id)
    if contrat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrat introuvable.")
    entite_type, entite_id = _journaliser(contrat)
    if entite_id is not None:
        await audit_engine.enregistrer_action(
            db, entite_type=entite_type, entite_id=entite_id,
            action="Contrat supprimé", details=contrat.fournisseur, auteur=user.nom_complet,
        )
    await db.delete(contrat)
    await db.commit()
