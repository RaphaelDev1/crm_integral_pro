# ==============================================================================
#  DEMARCHES ENGINE — logique métier des démarches post-vente (résiliation,
#  portabilité, changement de fournisseur, mandat, souscription) : quelles
#  démarches sont attendues pour un dossier, quels champs manquent, génération
#  du document PDF.
#
#  RÈGLE LÉGALE NON NÉGOCIABLE : `generer_document()` refuse (lève
#  `DemarcheEngineError`) tant que le mandat de représentation du client
#  (`Mandat.statut`) n'est pas "signe". Cette fonction ne lève jamais côté
#  HTTP : seule la tâche Celery (backend/workers/tasks.py) l'appelle et catch
#  l'exception pour marquer `Demarche.statut="echouee"` avec une note —
#  exactement comme `_envoyer_mandat_signature` le fait pour `Mandat.statut`.
# ==============================================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.client import Client
from backend.models.demarche import Demarche, TYPES_DEMARCHE
from backend.models.dossier import Dossier
from backend.models.mandat import Mandat
from backend.services import document_engine, storage_engine

FORMAT_DATE = "%d/%m/%Y %H:%M"


class DemarcheEngineError(Exception):
    """Refus métier (ex. mandat non signé, champs manquants) ou erreur de
    génération/stockage du document."""


# Univers → types de démarche attendus. Vocabulaire aligné sur
# `Dossier.univers` tel qu'utilisé par dossier_engine.documents_requis_pour_univers
# ("telecom_mobile", "telecom_box", "energie", "energie_pro",
# "assurance_habitation") — pas le vocabulaire français de src/constants.py,
# les deux systèmes restant indépendants.
MAPPING_UNIVERS_DEMARCHES: dict[str, list[str]] = {
    "telecom_mobile": ["mandat", "portabilite"],
    "telecom_box": ["mandat", "resiliation"],
    "energie": ["mandat", "changement_fournisseur"],
    "energie_pro": ["mandat", "changement_fournisseur"],
    "assurance_habitation": ["mandat", "souscription"],
}
_DEMARCHES_PAR_DEFAUT = ["mandat", "souscription"]

LABELS_TYPE_DEMARCHE: dict[str, str] = {
    "mandat": "Mandat de représentation",
    "resiliation": "Résiliation",
    "portabilite": "Portabilité mobile",
    "souscription": "Souscription",
    "changement_fournisseur": "Changement de fournisseur",
}


def demarches_requises(dossier: Dossier) -> list[str]:
    """Types de démarche attendus pour l'univers du dossier. Univers inconnu
    (vocabulaire libre, voir Dossier.univers) → repli sur une liste par
    défaut, jamais une liste vide."""
    return MAPPING_UNIVERS_DEMARCHES.get(dossier.univers, _DEMARCHES_PAR_DEFAUT)


def champs_manquants(demarche: Demarche) -> dict[str, dict]:
    """Sous-ensemble de `donnees_requises` dont `requis=True` et `valeur` vide."""
    return {
        cle: infos for cle, infos in (demarche.donnees_requises or {}).items()
        if infos.get("requis") and not infos.get("valeur")
    }


async def _mandat_signe_pour_dossier(db: AsyncSession, dossier: Dossier) -> Mandat | None:
    mandat = (await db.execute(
        select(Mandat).where(Mandat.client_id == dossier.client_id).order_by(Mandat.id.desc())
    )).scalars().first()
    return mandat if mandat and mandat.statut == "signe" else None


async def creer_demarche(db: AsyncSession, dossier: Dossier, type_demarche: str) -> Demarche:
    if type_demarche not in TYPES_DEMARCHE:
        raise DemarcheEngineError(f"Type de démarche inconnu : {type_demarche}")
    champs_template = document_engine.CHAMPS_REQUIS_PAR_TEMPLATE.get(type_demarche, {})
    demarche = Demarche(
        dossier_id=dossier.id,
        univers=dossier.univers,
        type_demarche=type_demarche,
        statut="a_generer",
        canal="lre",
        donnees_requises={cle: {"valeur": None, **infos} for cle, infos in champs_template.items()},
        date_creation=datetime.now().strftime(FORMAT_DATE),
    )
    db.add(demarche)
    await db.commit()
    await db.refresh(demarche)
    return demarche


async def marquer_champs(db: AsyncSession, demarche: Demarche, valeurs: dict[str, str]) -> Demarche:
    """Fusionne les valeurs soumises dans `donnees_requises` sans écraser les
    autres clés déjà présentes."""
    donnees = dict(demarche.donnees_requises or {})
    for cle, val in valeurs.items():
        if cle in donnees:
            donnees[cle] = {**donnees[cle], "valeur": val}
    demarche.donnees_requises = donnees
    await db.commit()
    await db.refresh(demarche)
    return demarche


async def generer_document(db: AsyncSession, demarche: Demarche) -> None:
    """Génère et stocke le PDF de la démarche. Ne lève jamais côté HTTP :
    catch par l'appelant (tâche Celery) qui marque `statut="echouee"`."""
    dossier = await db.get(Dossier, demarche.dossier_id)
    if dossier is None:
        raise DemarcheEngineError("Dossier introuvable.")

    mandat_signe = await _mandat_signe_pour_dossier(db, dossier)
    if mandat_signe is None:
        raise DemarcheEngineError(
            "Mandat de représentation non signé — génération de document refusée (obligation légale)."
        )

    manquants = champs_manquants(demarche)
    if manquants and demarche.type_demarche != "mandat":
        raise DemarcheEngineError(f"Champs manquants : {', '.join(manquants)}")

    client = await db.get(Client, dossier.client_id)
    if client is None:
        raise DemarcheEngineError("Client introuvable.")

    generateur = document_engine.GENERATEURS_PAR_TYPE.get(demarche.type_demarche)
    if generateur is None:
        raise DemarcheEngineError(f"Aucun générateur PDF pour le type « {demarche.type_demarche} ».")

    donnees_valeurs = {cle: infos.get("valeur") for cle, infos in (demarche.donnees_requises or {}).items()}
    pdf = generateur(dossier, client, donnees_valeurs)

    cle_s3 = storage_engine.upload_fichier(
        f"dossiers/{dossier.id}/demarches", demarche.type_demarche, pdf, f"{demarche.type_demarche}.pdf"
    )

    demarche.document_url = cle_s3
    demarche.statut = "generee"
    demarche.date_generation = datetime.now().strftime(FORMAT_DATE)
    if demarche.type_demarche == "mandat":
        demarche.mandat_id = mandat_signe.id
    await db.commit()


async def demarches_pour_dossier(db: AsyncSession, dossier_id: int) -> list[Demarche]:
    return (await db.execute(select(Demarche).where(Demarche.dossier_id == dossier_id))).scalars().all()
