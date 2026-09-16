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
from backend.models.mandat import Mandat
from backend.models.mandat_honoraires import MandatHonoraires
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

# Séquence "heureuse" de la timeline affichée au client (voir
# construire_timeline) — partagée avec dossier_a_depasse_etape ci-dessous
# pour savoir si un dossier a atteint (ou dépassé) une étape donnée, sans
# dupliquer cet ordre à chaque appelant (ex. backend/routers/portail_public.py).
ETAPES_TIMELINE: list[tuple[str, str]] = [
    ("docs_demandes",       "Nous vous demandons vos documents"),
    ("docs_recus",          "Documents vérifiés"),
    ("mandat_a_signer",     "Mandat de représentation signé"),
    ("mandat_signe",        "Mandat honoraires signé"),
    ("soumis_fournisseur",  "Envoi de votre dossier au fournisseur"),
    ("en_activation",       "Activation en cours"),
    ("actif",               "Votre nouvelle offre est active"),
]


def dossier_a_depasse_etape(dossier: Dossier, etape: str) -> bool:
    """Vrai si `dossier.statut` a atteint ou dépassé `etape` dans la séquence
    ETAPES_TIMELINE (ex. `dossier_a_depasse_etape(dossier, "soumis_fournisseur")`
    pour savoir si le dossier a été envoyé au fournisseur). Faux pour un
    dossier en échec/annulé (hors séquence)."""
    ordre_index = {cle: i for i, (cle, _) in enumerate(ETAPES_TIMELINE)}
    idx_cible = ordre_index.get(etape, -1)
    idx_actuel = ordre_index.get(dossier.statut, -1)
    return idx_actuel != -1 and idx_cible != -1 and idx_actuel >= idx_cible


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
    if nouveau_statut == ancien_statut:
        # No-op idempotent plutôt qu'une TransitionInvalide : peut arriver quand
        # une transition manuelle (bouton conseiller) et une transition
        # automatique (ex. dernier document validé, voir
        # clients.py::valider_document) visent le même statut à quelques
        # secondes d'écart — le dossier est déjà dans l'état voulu, ce n'est
        # pas une erreur pour l'utilisateur.
        return dossier
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


def _plus_recente(dates: list[str | None]) -> str | None:
    """Renvoie la date la plus récente d'une liste de chaînes FORMAT_DATE,
    en ignorant les valeurs absentes/non parsables (comparaison lexicale
    incorrecte sur "%d/%m/%Y %H:%M", d'où le passage par strptime)."""
    valeurs: list[tuple[datetime, str]] = []
    for d in dates:
        if not d:
            continue
        try:
            valeurs.append((datetime.strptime(d, FORMAT_DATE), d))
        except ValueError:
            continue
    return max(valeurs)[1] if valeurs else None


async def signaux_timeline(db: AsyncSession, dossier: Dossier) -> dict:
    """Rassemble tous les signaux métier consommés par `construire_timeline`,
    factorisé pour éviter la duplication (et la divergence) entre
    backend/routers/dossiers.py::obtenir_timeline_dossier et
    backend/routers/portail_public.py::suivi_dossier, qui construisaient
    auparavant chacun leur propre requête `mandat_envoye` sans jamais
    interroger `MandatHonoraires`.

    Inclut aussi la date réelle de chaque signal (upload/validation de
    document, envoi/signature de mandat) — auparavant `construire_timeline`
    ne datait ces étapes que via `dossier.notes_workflow`, alimenté
    uniquement par des transitions manuelles explicites (`transiter()`), ce
    qui laissait "Documents vérifiés" ou "Mandat de représentation signé"
    sans date la plupart du temps alors que l'événement réel avait bien une
    date connue."""
    documents = (
        await db.execute(select(Document).where(Document.client_id == dossier.client_id))
    ).scalars().all()
    documents_recus = len(documents) > 0
    documents_valides, _ = await documents_valides_pour_client(db, dossier.client_id)
    date_docs_recus = _plus_recente([d.date_upload for d in documents])
    date_docs_valides = _plus_recente([d.date_validation for d in documents])

    mandat = (
        await db.execute(
            select(Mandat).where(Mandat.client_id == dossier.client_id).order_by(Mandat.id.desc()).limit(1)
        )
    ).scalars().first()
    mandat_envoye = mandat is not None and mandat.statut in ("envoye", "recu", "signe")
    mandat_representation_signe = mandat is not None and mandat.statut == "signe"

    mandat_honoraires = (
        await db.execute(select(MandatHonoraires).where(MandatHonoraires.dossier_id == dossier.id))
    ).scalar_one_or_none()
    mandat_honoraires_envoye = mandat_honoraires is not None and mandat_honoraires.statut in ("envoye", "signe")
    mandat_honoraires_signe = mandat_honoraires is not None and mandat_honoraires.statut == "signe"

    return {
        "documents_recus": documents_recus,
        "documents_valides": documents_valides,
        "date_docs_recus": date_docs_recus,
        "date_docs_valides": date_docs_valides,
        "mandat_envoye": mandat_envoye,
        "mandat_representation_signe": mandat_representation_signe,
        "date_mandat_envoye": mandat.date_envoi if mandat else None,
        "date_mandat_signe": mandat.date_signature if mandat else None,
        "mandat_honoraires_envoye": mandat_honoraires_envoye,
        "mandat_honoraires_signe": mandat_honoraires_signe,
        "date_mandat_honoraires_envoye": mandat_honoraires.date_creation if mandat_honoraires else None,
        "date_mandat_honoraires_signe": mandat_honoraires.date_signature if mandat_honoraires else None,
    }


def construire_timeline(
    dossier: Dossier,
    documents_recus: bool = False,
    mandat_envoye: bool = False,
    documents_valides: bool = False,
    mandat_representation_signe: bool = False,
    mandat_honoraires_envoye: bool = False,
    mandat_honoraires_signe: bool = False,
    date_docs_recus: str | None = None,
    date_docs_valides: str | None = None,
    date_mandat_envoye: str | None = None,
    date_mandat_signe: str | None = None,
    date_mandat_honoraires_envoye: str | None = None,
    date_mandat_honoraires_signe: str | None = None,
) -> list[dict]:
    """Retourne la timeline à afficher au client dans son portail (et au
    conseiller sur la fiche dossier).

    Les étapes "docs_recus", "mandat_a_signer" et "mandat_signe" sont pilotées
    directement par leur propre signal métier (documents reçus/validés côté
    conseiller, mandat de représentation envoyé/signé côté Yousign, mandat
    honoraires envoyé/signé), **indépendamment** de la position de
    `dossier.statut` dans `ordre` — un dossier resté en retard sur son statut
    grossier (ex. le conseiller a généré/envoyé un mandat sans avoir cliqué le
    bouton de transition manuelle) ne doit jamais faire apparaître ces étapes
    comme non commencées alors que l'événement réel a bien eu lieu :
      - "docs_demandes" ("Nous vous demandons vos documents") : affichée orange
        ("en cours") dès la création du dossier, avant même toute action —
        c'est la première chose que le conseiller doit faire, elle ne doit pas
        rester grise ("à venir") comme si rien n'était encore attendu. Dès
        l'envoi de la demande (email/SMS/lien copié), l'action du conseiller
        est terminée — ce n'est plus lui qui doit encore agir, donc vert
        immédiatement plutôt qu'"en cours".
      - "docs_recus" ("Documents vérifiés") : orange dès qu'au moins un
        document a été transmis par le client (`documents_recus`), vert dès
        que tous les documents requis sont au statut "valide"
        (`documents_valides`, voir dossier_engine.documents_valides_pour_client).
      - "mandat_a_signer" ("Mandat de représentation signé") : orange dès
        l'envoi du mandat en signature (`mandat_envoye`, affiché "Mandat
        envoyé"), vert uniquement une fois réellement signé
        (`mandat_representation_signe`).
      - "mandat_signe" ("Mandat honoraires signé") : orange dès l'envoi du
        mandat honoraires (`mandat_honoraires_envoye`), vert une fois signé
        (`mandat_honoraires_signe`).
    Les étapes sans signal dédié ("soumis_fournisseur", "en_activation",
    "actif") restent pilotées par la seule position de `dossier.statut`.
    """
    ordre = ETAPES_TIMELINE
    statut_actuel = dossier.statut
    ordre_index = {k: i for i, (k, _) in enumerate(ordre)}
    idx_actuel = ordre_index.get(statut_actuel, -1)

    dates_par_statut = {}
    for entree in (dossier.notes_workflow or []):
        dates_par_statut[entree.get("vers")] = entree.get("date")

    derniere_etape = len(ordre) - 1

    etapes = []
    for i, (cle, label) in enumerate(ordre):
        date_override: str | None = None
        if cle == "docs_recus":
            if documents_valides:
                statut_etape = "termine"
                date_override = date_docs_valides
            elif documents_recus:
                statut_etape = "en_cours"
                date_override = date_docs_recus
            elif i < idx_actuel:
                statut_etape = "termine"
            elif i == idx_actuel:
                statut_etape = "en_cours"
            else:
                statut_etape = "a_venir"
        elif cle == "mandat_a_signer":
            if mandat_representation_signe:
                statut_etape = "termine"
                date_override = date_mandat_signe
            elif mandat_envoye:
                statut_etape = "en_cours"
                date_override = date_mandat_envoye
            elif i < idx_actuel:
                statut_etape = "termine"
            elif i == idx_actuel:
                statut_etape = "en_cours"
            else:
                statut_etape = "a_venir"
        elif cle == "mandat_signe":
            if mandat_honoraires_signe:
                statut_etape = "termine"
                date_override = date_mandat_honoraires_signe
            elif mandat_honoraires_envoye:
                statut_etape = "en_cours"
                date_override = date_mandat_honoraires_envoye
            elif i < idx_actuel:
                statut_etape = "termine"
            elif i == idx_actuel:
                statut_etape = "en_cours"
            else:
                statut_etape = "a_venir"
        elif i < idx_actuel or (i == idx_actuel == derniere_etape):
            # La dernière étape ("actif") n'a pas d'étape suivante pour la faire
            # basculer à "termine" par le test `i < idx_actuel` normal — dès
            # qu'elle est atteinte, elle est donc terminée, pas "en cours".
            statut_etape = "termine"
        elif cle == "docs_demandes" and i == idx_actuel:
            statut_etape = "termine"
        elif cle == "docs_demandes" and idx_actuel == -1 and i == 0:
            statut_etape = "en_cours"
        elif i == idx_actuel:
            statut_etape = "en_cours"
        else:
            statut_etape = "a_venir"
        label_affiche = "Mandat envoyé" if cle == "mandat_a_signer" and statut_etape == "en_cours" else label
        etapes.append({
            "cle": cle,
            "label": label_affiche,
            "statut": statut_etape,
            "date": date_override or dates_par_statut.get(cle),
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
