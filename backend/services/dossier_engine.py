# ==============================================================================
#  DOSSIER ENGINE — machine à états stricte pour le workflow de souscription.
#
#  Transitions autorisées :
#
#   initie ──► docs_demandes ──► docs_recus ──► mandat_a_signer ──►
#     mandat_signe ──► soumis_fournisseur ──► en_activation ──►
#     actif ──► facture
#
#  N'importe quel état non-terminal peut aussi transiter vers :
#    - echec (échec fournisseur/technique)
#    - annule (client renonce)
# ==============================================================================
from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.dossier import Dossier
from backend.services.dossier_notifications import SEUILS_JOURS_PAR_STATUT


FORMAT_DATE = "%d/%m/%Y %H:%M"


TRANSITIONS_AUTORISEES: dict[str, set[str]] = {
    "initie":              {"docs_demandes", "annule"},
    "docs_demandes":       {"docs_recus", "annule", "echec"},
    "docs_recus":          {"mandat_a_signer", "annule", "echec"},
    "mandat_a_signer":     {"mandat_signe", "annule", "echec"},
    "mandat_signe":        {"soumis_fournisseur", "annule", "echec"},
    "soumis_fournisseur":  {"en_activation", "echec"},
    "en_activation":       {"actif", "echec"},
    "actif":               {"facture"},
    "facture":             set(),
    "echec":               set(),
    "annule":              set(),
}


class TransitionInvalide(Exception):
    """La transition demandée n'est pas autorisée depuis l'état actuel."""


def peut_transiter(depuis: str, vers: str) -> bool:
    return vers in TRANSITIONS_AUTORISEES.get(depuis, set())


async def transiter(
    db: AsyncSession,
    dossier: Dossier,
    nouveau_statut: str,
    *,
    par: str = "systeme",
    commentaire: str | None = None,
    on_transition: Callable[[Dossier, str], None] | None = None,
) -> Dossier:
    """Effectue la transition d'état, journalise et met à jour les dates clés."""
    ancien_statut = dossier.statut
    if not peut_transiter(ancien_statut, nouveau_statut):
        raise TransitionInvalide(
            f"Transition invalide : {ancien_statut} → {nouveau_statut}. "
            f"Transitions possibles : {sorted(TRANSITIONS_AUTORISEES.get(ancien_statut, set()))}"
        )

    now_str = datetime.now().strftime(FORMAT_DATE)
    dossier.statut = nouveau_statut
    dossier.date_derniere_transition = now_str

    if nouveau_statut == "soumis_fournisseur":
        dossier.date_soumission = now_str
    elif nouveau_statut == "actif":
        dossier.date_activation_reelle = now_str

    entree = {
        "date": now_str,
        "type": "transition",
        "de": ancien_statut,
        "vers": nouveau_statut,
        "par": par,
    }
    if commentaire:
        entree["commentaire"] = commentaire
    dossier.notes_workflow = (dossier.notes_workflow or []) + [entree]

    if on_transition:
        on_transition(dossier, ancien_statut)

    await db.commit()
    await db.refresh(dossier)
    return dossier


async def ajouter_note(db: AsyncSession, dossier: Dossier, texte: str, *, par: str) -> Dossier:
    """Ajoute une note manuelle au journal du dossier, sans changer son statut
    (ex. compte-rendu d'appel, remarque conseiller) — même flux chronologique
    que les transitions, distingué par `type: "note"`."""
    entree = {
        "date": datetime.now().strftime(FORMAT_DATE),
        "type": "note",
        "texte": texte,
        "par": par,
    }
    dossier.notes_workflow = (dossier.notes_workflow or []) + [entree]
    await db.commit()
    await db.refresh(dossier)
    return dossier


def documents_requis_pour_univers(univers: str) -> list[dict]:
    """Retourne la liste des documents à demander au client pour un univers donné."""
    base = [
        {"type_document": "cni", "label_affiche": "Pièce d'identité (recto + verso)"},
        {"type_document": "rib", "label_affiche": "RIB"},
    ]
    if univers in ("telecom_box", "energie", "energie_pro", "assurance_habitation"):
        base.insert(1, {"type_document": "justificatif_domicile", "label_affiche": "Justificatif de domicile (< 3 mois)"})
    return base


def construire_timeline(dossier: Dossier) -> list[dict]:
    """Retourne la timeline à afficher au client dans son portail."""
    ordre = [
        ("docs_demandes",       "Nous vous demandons vos documents"),
        ("docs_recus",          "Documents vérifiés"),
        ("mandat_a_signer",     "Signature de votre mandat"),
        ("mandat_signe",        "Mandat signé"),
        ("soumis_fournisseur",  "Envoi de votre dossier au fournisseur"),
        ("en_activation",       "Activation en cours"),
        ("actif",               "Votre nouvelle offre est active"),
    ]
    statut_actuel = dossier.statut
    ordre_index = {k: i for i, (k, _) in enumerate(ordre)}
    idx_actuel = ordre_index.get(statut_actuel, -1)

    dates_par_statut = {}
    for entree in (dossier.notes_workflow or []):
        dates_par_statut[entree.get("vers")] = entree.get("date")

    etapes = []
    for i, (cle, label) in enumerate(ordre):
        if i < idx_actuel:
            statut_etape = "termine"
        elif i == idx_actuel:
            statut_etape = "en_cours"
        else:
            statut_etape = "a_venir"
        etapes.append({
            "cle": cle,
            "label": label,
            "statut": statut_etape,
            "date": dates_par_statut.get(cle),
            "icone": "check" if statut_etape == "termine" else ("clock" if statut_etape == "en_cours" else "circle"),
        })
    return etapes


_JOURS_MIN_ENTRE_RELANCES = 3


def _jours_ecoules(date_str: str | None) -> float | None:
    if not date_str:
        return None
    try:
        return (datetime.now() - datetime.strptime(date_str, FORMAT_DATE)).total_seconds() / 86400
    except ValueError:
        return None


async def dossiers_stagnants(db: AsyncSession) -> list[Dossier]:
    """Dossiers dont le statut a un seuil de stagnation configuré
    (`dossier_notifications.SEUILS_JOURS_PAR_STATUT`) et qui n'ont pas bougé
    depuis plus longtemps que ce seuil — candidats à une relance
    automatique. Exclut les dossiers relancés il y a moins de
    `_JOURS_MIN_ENTRE_RELANCES` jours pour éviter le spam."""
    statuts_suivis = list(SEUILS_JOURS_PAR_STATUT.keys())
    result = await db.execute(select(Dossier).where(Dossier.statut.in_(statuts_suivis)))
    candidats = []
    for dossier in result.scalars().all():
        seuil = SEUILS_JOURS_PAR_STATUT[dossier.statut]
        reference = dossier.date_derniere_transition or dossier.date_creation
        jours_depuis_transition = _jours_ecoules(reference)
        if jours_depuis_transition is None or jours_depuis_transition < seuil:
            continue
        jours_depuis_relance = _jours_ecoules(dossier.derniere_relance_envoyee_le)
        if jours_depuis_relance is not None and jours_depuis_relance < _JOURS_MIN_ENTRE_RELANCES:
            continue
        candidats.append(dossier)
    return candidats
