# ==============================================================================
#  CATALOGUE (IA Conseil) — lecture publique (conseiller) des offres actives
#  + CRUD admin minimal. PLAN_IMPLEMENTATION_4_PHASES.md §0.5 : le CRUD
#  complet avec workflow brouillon→validée→publiée et import CSV est prévu
#  Phase 1 §1.4.C ; ce routeur pose seulement le contrat CRUD de base.
# ==============================================================================
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user, require_role
from backend.models.ia_conseil import Categorie, Fournisseur, OffreConseil, RapportVeilleMarche
from backend.schemas.ia_conseil import (
    CategorieOut,
    FournisseurOut,
    OffreConseilCreate,
    OffreConseilOut,
    OffreConseilUpdate,
    RapportVeilleMarcheOut,
)

router = APIRouter(prefix="/api/v1/catalogue", tags=["ia_conseil_catalogue"], dependencies=[Depends(get_current_user)])
admin_router = APIRouter(
    prefix="/api/v1/admin", tags=["ia_conseil_admin"], dependencies=[Depends(require_role("Admin"))]
)


@router.get("/categories", response_model=list[CategorieOut])
async def lister_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Categorie).where(Categorie.actif.is_(True)).order_by(Categorie.ordre))
    return result.scalars().all()


@router.get("/fournisseurs", response_model=list[FournisseurOut])
async def lister_fournisseurs(categorie: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Fournisseur)
    if categorie:
        query = query.where(Fournisseur.categorie_slug == categorie)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/offres", response_model=list[OffreConseilOut])
async def lister_offres(categorie: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(OffreConseil).where(OffreConseil.valide.is_(True))
    if categorie:
        query = query.where(OffreConseil.categorie_slug == categorie)
    result = await db.execute(query.order_by(OffreConseil.prix_mensuel))
    return result.scalars().all()


@admin_router.post("/offres", response_model=OffreConseilOut, status_code=status.HTTP_201_CREATED)
async def creer_offre(payload: OffreConseilCreate, db: AsyncSession = Depends(get_db)):
    offre = OffreConseil(**payload.model_dump())
    db.add(offre)
    await db.commit()
    await db.refresh(offre)
    return offre


@admin_router.put("/offres/{offre_id}", response_model=OffreConseilOut)
async def maj_offre(offre_id: uuid.UUID, payload: OffreConseilUpdate, db: AsyncSession = Depends(get_db)):
    offre = await db.get(OffreConseil, offre_id)
    if offre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offre introuvable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(offre, champ, valeur)
    await db.commit()
    await db.refresh(offre)
    return offre


@admin_router.delete("/offres/{offre_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_offre(offre_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    offre = await db.get(OffreConseil, offre_id)
    if offre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offre introuvable.")
    await db.delete(offre)
    await db.commit()


# ==============================================================================
#  VEILLE MARCHÉ (§3.4) — revue des rapports hebdomadaires de l'agent
#  autonome (veille_marche_agent.py) et intégration d'une offre détectée au
#  catalogue, en brouillon (valide=False) pour une dernière vérification
#  manuelle avant publication via PUT /offres/{id} ci-dessus.
# ==============================================================================
@admin_router.get("/veille-marche/rapports", response_model=list[RapportVeilleMarcheOut])
async def lister_rapports_veille_marche(statut: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(RapportVeilleMarche)
    if statut:
        query = query.where(RapportVeilleMarche.statut == statut)
    result = await db.execute(query.order_by(RapportVeilleMarche.cree_le.desc()))
    return result.scalars().all()


@admin_router.post("/veille-marche/rapports/{rapport_id}/offres/{index}/integrer", response_model=OffreConseilOut)
async def integrer_offre_veille_marche(rapport_id: uuid.UUID, index: int, db: AsyncSession = Depends(get_db)):
    """Crée une OffreConseil brouillon (valide=False) à partir de l'entrée
    `index` du rapport — ne publie jamais automatiquement, une revue admin
    (prix, fournisseur canonique) reste nécessaire avant PUT .../valide=true."""
    rapport = await db.get(RapportVeilleMarche, rapport_id)
    if rapport is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rapport introuvable.")
    offres = rapport.offres_detectees or []
    if index < 0 or index >= len(offres):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offre détectée introuvable dans ce rapport.")
    entree = offres[index]

    fournisseur = None
    if entree.get("fournisseur"):
        fournisseur = (
            await db.execute(
                select(Fournisseur).where(
                    Fournisseur.nom == entree["fournisseur"], Fournisseur.categorie_slug == rapport.categorie_slug
                )
            )
        ).scalars().first()

    offre = OffreConseil(
        fournisseur_id=fournisseur.id if fournisseur else None,
        categorie_slug=rapport.categorie_slug,
        nom=entree.get("nom_offre") or "Offre détectée (veille marché)",
        prix_mensuel=entree.get("prix_mensuel"),
        engagement_mois=0,
        frais_mise_en_service=0,
        caracteristiques={"description": entree.get("caracteristiques") or ""},
        conditions={"url_source": entree.get("url_source"), "confiance": entree.get("confiance")},
        source="veille_marche",
        source_ref=str(rapport.id),
        valide=False,
    )
    db.add(offre)
    await db.commit()
    await db.refresh(offre)
    return offre
