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

from backend.models.document import Document
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
    """Retourne la liste des documents à demander pour un univers donné, dès
    qu'un dossier existe — la collecte CNI/RIB/justificatif se fait en
    parallèle de la signature du mandat, plutôt que d'attendre celle-ci (avant,
    `Dossier.est_prospect` bloquait cette demande jusqu'à la conversion
    officielle ; ça ralentissait inutilement le dossier). Le lien prospect
    "léger" (facture/speedtest, avant même qu'un dossier existe) reste géré à
    part, voir backend/routers/portail_public.py::_contexte_token_prospect."""
    base = [
        {"type_document": "cni", "label_affiche": "Pièce d'identité (recto + verso)"},
        {"type_document": "rib", "label_affiche": "RIB"},
    ]
    if univers in ("telecom_box", "energie", "energie_pro", "assurance_habitation"):
        base.insert(1, {"type_document": "justificatif_domicile", "label_affiche": "Justificatif de domicile (< 3 mois)"})
    return base


async def documents_valides_pour_client(db: AsyncSession, client_id: int) -> tuple[bool, list[str]]:
    """Vérifie que tous les documents KYC requis (CNI/RIB/justificatif, selon
    l'univers de chacun des dossiers du client) sont au statut "valide" — sert
    de condition à la conversion prospect→client à la signature du mandat
    (voir mandat_engine.traiter_mandat_signe) : la signature seule ne suffit
    plus, les documents doivent aussi avoir été envoyés et validés. Retourne
    (True, []) si tout est validé, sinon (False, types_manquants)."""
    dossiers = (
        await db.execute(select(Dossier).where(Dossier.client_id == client_id))
    ).scalars().all()

    types_requis: set[str] = set()
    for dossier in dossiers:
        types_requis.update(d["type_document"] for d in documents_requis_pour_univers(dossier.univers))
    if not types_requis:
        return True, []

    documents = (
        await db.execute(select(Document).where(Document.client_id == client_id))
    ).scalars().all()
    types_valides = {d.type_document for d in documents if d.statut_kyc == "valide"}

    manquants = sorted(types_requis - types_valides)
    return not manquants, manquants


def construire_timeline(dossier: Dossier, documents_recus: bool = False) -> list[dict]:
    """Retourne la timeline à afficher au client dans son portail (et au
    conseiller sur la fiche dossier).

    Deux étapes ont un statut dérivé d'un événement plutôt que de la seule
    position dans `ordre` :
      - "docs_demandes" ("Nous vous demandons vos documents") : dès l'envoi de
        la demande (email/SMS/lien copié), l'action du conseiller est
        terminée — ce n'est pas lui qui doit encore agir, donc vert
        immédiatement plutôt qu'"en cours".
      - "docs_recus" ("Documents vérifiés") : passe orange dès qu'au moins un
        document a été transmis par le client (`documents_recus`, détecté par
        la notification d'upload), même si le conseiller n'a pas encore fait
        transiter le dossier vers "docs_recus" — l'attente réelle porte sur la
        vérification, pas sur la demande initiale.
    """
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

    derniere_etape = len(ordre) - 1

    etapes = []
    for i, (cle, label) in enumerate(ordre):
        if i < idx_actuel or (i == idx_actuel == derniere_etape):
            # La dernière étape ("actif") n'a pas d'étape suivante pour la faire
            # basculer à "termine" par le test `i < idx_actuel` normal — dès
            # qu'elle est atteinte, elle est donc terminée, pas "en cours".
            statut_etape = "termine"
        elif cle == "docs_demandes" and i == idx_actuel:
            statut_etape = "termine"
        elif cle == "docs_recus" and i == idx_actuel + 1 and documents_recus:
            statut_etape = "en_cours"
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
    # Plus grosses économies en premier — priorise les dossiers les plus
    # rentables à faire avancer ; à économie égale, le plus ancien d'abord
    # (celui qui stagne depuis le plus longtemps est le plus urgent).
    def _cle_tri(d: Dossier) -> tuple[float, float]:
        try:
            horodatage = datetime.strptime(d.date_creation, FORMAT_DATE).timestamp() if d.date_creation else float("inf")
        except ValueError:
            horodatage = float("inf")
        return (-(d.economie_annuelle_estimee or 0), horodatage)

    candidats.sort(key=_cle_tri)
    return candidats
