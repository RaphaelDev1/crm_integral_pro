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
from backend.models.contrat import Contrat
from backend.models.demarche import Demarche, TYPES_DEMARCHE
from backend.models.dossier import Dossier
from backend.models.mandat import Mandat
from backend.services import document_engine, storage_engine

# Champs de la démarche "portabilite" à recopier sur la ligne mobile de
# référence (Contrat) — c'est cette table que lit l'aide-mémoire souscription
# (frontend-conseiller/app/souscription-reference/page.tsx via useContrats),
# jamais Demarche.donnees_requises. Sans cette synchronisation, les réponses
# saisies via le questionnaire de démarche (post-lancement dossier) restent
# invisibles de l'aide-mémoire alors qu'elles y apparaissent quand elles sont
# saisies plus tôt, côté prospect (portail_public.py::renseigner_situation_actuelle).
CHAMPS_PORTABILITE_VERS_CONTRAT = ("conserver_numero", "rio", "numero_ligne", "type_sim")

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
    # "audit_*" en tête : c'est la trame adaptative par secteur (voir
    # docs/QUESTIONS_PAR_SECTEUR.md) que le client doit compléter avant de
    # pouvoir uploader ses documents — voir audit_secteur_complet ci-dessous
    # et portail_public.py::uploader_document.
    "telecom_mobile": ["audit_mobile", "mandat", "portabilite"],
    "telecom_box": ["audit_box", "mandat", "resiliation"],
    "energie": ["audit_energie", "mandat", "changement_fournisseur"],
    "energie_pro": ["audit_energie", "mandat", "changement_fournisseur"],
    "assurance_habitation": ["mandat", "souscription"],
}
_DEMARCHES_PAR_DEFAUT = ["mandat", "souscription"]

LABELS_TYPE_DEMARCHE: dict[str, str] = {
    "mandat": "Mandat de représentation",
    "resiliation": "Résiliation",
    "portabilite": "Portabilité mobile",
    "souscription": "Souscription",
    "changement_fournisseur": "Changement de fournisseur",
    "audit_mobile": "Audit mobile",
    "audit_box": "Audit box / TV",
    "audit_energie": "Audit énergie",
}

# Types de démarche qui constituent la trame adaptative par secteur exposée
# au client avant l'upload de documents — voir audit_secteur_complet.
TYPES_QUESTIONNAIRE_SECTEUR = frozenset({"audit_mobile", "audit_box", "audit_energie", "portabilite"})


def demarches_requises(dossier: Dossier) -> list[str]:
    """Types de démarche attendus pour l'univers du dossier. Univers inconnu
    (vocabulaire libre, voir Dossier.univers) → repli sur une liste par
    défaut, jamais une liste vide."""
    return MAPPING_UNIVERS_DEMARCHES.get(dossier.univers, _DEMARCHES_PAR_DEFAUT)


def champs_manquants(demarche: Demarche) -> dict[str, dict]:
    """Sous-ensemble de `donnees_requises` dont le champ est effectivement requis
    et `valeur` vide.

    Un champ peut porter `requis_si: {"champ": cle, "egal": valeur}` (ex. le RIO
    n'est requis que si le prospect a choisi de conserver son numero, voir
    document_engine.CHAMPS_REQUIS_PAR_TEMPLATE["portabilite"]) — dans ce cas
    `requis` seul ne suffit pas, il faut aussi que le champ dont il dépend ait
    déjà la valeur attendue."""
    donnees = demarche.donnees_requises or {}

    def _requis_effectif(infos: dict) -> bool:
        if not infos.get("requis"):
            return False
        condition = infos.get("requis_si")
        if not condition:
            return True
        valeur_dependance = (donnees.get(condition["champ"]) or {}).get("valeur")
        return valeur_dependance == condition["egal"]

    return {
        cle: infos for cle, infos in donnees.items()
        if _requis_effectif(infos) and not infos.get("valeur")
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

    if demarche.type_demarche == "portabilite":
        await _synchroniser_contrat_portabilite(db, demarche, donnees)

    await db.commit()
    await db.refresh(demarche)
    return demarche


async def _synchroniser_contrat_portabilite(db: AsyncSession, demarche: Demarche, donnees: dict) -> None:
    """Recopie conserver_numero/rio/numero_ligne/type_sim sur la ligne mobile
    de référence du client (même sélection que le frontend : ligne_principale
    en priorité, sinon la première ligne "Forfait mobile" trouvée)."""
    dossier = await db.get(Dossier, demarche.dossier_id)
    if dossier is None or dossier.client_id is None:
        return
    lignes_mobiles = (await db.execute(
        select(Contrat)
        .where(Contrat.client_id == dossier.client_id, Contrat.categorie == "Forfait mobile")
        .order_by(Contrat.ligne_principale.desc(), Contrat.id)
    )).scalars().all()
    if not lignes_mobiles:
        return
    ligne_mobile = lignes_mobiles[0]
    for cle in CHAMPS_PORTABILITE_VERS_CONTRAT:
        valeur = (donnees.get(cle) or {}).get("valeur")
        if valeur:
            setattr(ligne_mobile, cle, valeur)


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


async def creer_demarches_manquantes(db: AsyncSession, dossier: Dossier) -> list[Demarche]:
    """Crée les démarches requises par l'univers du dossier (voir
    MAPPING_UNIVERS_DEMARCHES) qui n'existent pas encore. Appelé quand le lien
    client est généré/envoyé (voir routers/dossiers.py) pour garantir que la
    trame de questions (audit_*/portabilite) et les autres démarches attendues
    existent bien pour le client, sans que le conseiller ait à les créer une
    par une depuis l'onglet Démarches."""
    types_existants = {d.type_demarche for d in await demarches_pour_dossier(db, dossier.id)}
    return [
        await creer_demarche(db, dossier, type_demarche)
        for type_demarche in demarches_requises(dossier)
        if type_demarche not in types_existants
    ]


def audit_secteur_complet(demarches: list[Demarche]) -> bool:
    """Vrai si toutes les démarches de la trame adaptative par secteur
    (TYPES_QUESTIONNAIRE_SECTEUR) rattachées au dossier n'ont plus de champ
    manquant, ou si aucune n'y est rattachée (secteur non couvert par la
    trame, ex. assurance_habitation). Utilisé pour bloquer l'upload de
    documents tant que le client n'a pas répondu — voir
    portail_public.py::uploader_document et ::contexte_token."""
    for demarche in demarches:
        if demarche.statut != "a_generer":
            continue
        if demarche.type_demarche not in TYPES_QUESTIONNAIRE_SECTEUR:
            continue
        if champs_manquants(demarche):
            return False
    return True
