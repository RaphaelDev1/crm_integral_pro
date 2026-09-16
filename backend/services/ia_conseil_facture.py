# ==============================================================================
#  IA_CONSEIL_FACTURE — upload de facture pendant une session de trame,
#  analyse via facture_analyzer.py (réutilisé tel quel, déjà utilisé pour le
#  CRM legacy) et proposition d'auto-remplissage des réponses (§3.1). Le
#  conseiller valide/corrige toujours avant application — voir appliquer().
# ==============================================================================
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ia_conseil import SessionFacture, SessionTrame
from backend.services import ia_conseil_engine as engine
from backend.services import storage_engine
from backend.services.facture_analyzer import FactureAnalyzerError, MIME_AUTORISES_FACTURE, analyser_facture

# Mappe chaque id de question de trame vers le champ extrait de la facture
# (backend/services/facture_analyzer.py::CHAMPS_FACTURE) qui peut l'auto-
# remplir. Seules les correspondances fiables sont listées — aucune
# consommation en kWh n'est extraite des factures énergie actuellement, donc
# pas de mapping pour consommation_elec_kwh_an/consommation_gaz_kwh_an
# (mieux vaut ne rien proposer qu'une valeur devinée).
MAPPING_PAR_CATEGORIE: dict[str, dict[str, str]] = {
    "mobile": {
        "operateur_actuel": "operateur",
        "cout_actuel_mensuel": "prix_ttc",
        "conso_data_go": "data_conso_go",
    },
    "box": {
        "operateur_actuel": "operateur",
        "cout_actuel_mensuel": "prix_ttc",
    },
    "energie_elec": {
        "fournisseur_actuel_elec": "operateur",
        "cout_actuel_mensuel_elec": "prix_ttc",
    },
    "energie_gaz": {
        "fournisseur_actuel_gaz": "operateur",
        "cout_actuel_mensuel_gaz": "prix_ttc",
    },
}


def mapper_extraction_vers_reponses(categorie_slug: str, extraction: dict[str, Any]) -> dict[str, Any]:
    """Propose des réponses de trame à partir d'une extraction de facture —
    ignore les champs vides/nuls/zéro (mieux vaut ne rien proposer qu'une
    valeur fausse)."""
    mapping = MAPPING_PAR_CATEGORIE.get(categorie_slug, {})
    propositions: dict[str, Any] = {}
    for question_id, champ in mapping.items():
        valeur = extraction.get(champ)
        if valeur in (None, "", 0, 0.0):
            continue
        propositions[question_id] = valeur
    return propositions


async def televerser(db: AsyncSession, session: SessionTrame, contenu: bytes, nom_fichier: str) -> SessionFacture:
    if not contenu:
        raise ValueError("Fichier vide.")
    # Détection par contenu réel (magic bytes), pas par l'extension du nom de
    # fichier — accepte aussi les photos de facture (JPG/PNG), comme le
    # portail client le propose déjà.
    if storage_engine.deviner_mime_reel(contenu) not in MIME_AUTORISES_FACTURE:
        raise ValueError("Format non supporté (PDF, JPG, PNG ou WEBP attendu).")

    cle = storage_engine.upload_fichier(
        f"ia-conseil/sessions/{session.id}/factures", "facture", contenu, nom_fichier
    )

    facture = SessionFacture(
        session_id=session.id,
        categorie_slug=session.categorie_slug,
        storage_key=cle,
        nom_fichier=nom_fichier,
        statut="en_attente",
    )
    db.add(facture)
    await db.flush()
    return facture


async def analyser(db: AsyncSession, facture: SessionFacture) -> SessionFacture:
    """Télécharge le fichier stocké et l'analyse via facture_analyzer (Claude
    vision) — ne modifie jamais SessionTrame.reponses directement, se
    contente de proposer des valeurs (voir appliquer())."""
    try:
        contenu = storage_engine.telecharger_document(facture.storage_key)
    except storage_engine.StorageError as exc:
        facture.statut = "echouee"
        facture.erreur = str(exc)
        await db.flush()
        return facture

    # Nom de fichier fixe pour l'écriture temporaire : `nom_fichier` vient
    # d'un upload utilisateur et ne doit jamais être utilisé comme segment de
    # chemin (traversal via "../"). L'extension n'a pas d'incidence sur
    # l'analyse : analyser_facture() détecte le format par le contenu réel.
    with tempfile.TemporaryDirectory() as tmp:
        chemin = Path(tmp) / "facture.bin"
        chemin.write_bytes(contenu)
        try:
            extraction = analyser_facture(chemin)
        except FactureAnalyzerError as exc:
            facture.statut = "echouee"
            facture.erreur = str(exc)
            await db.flush()
            return facture

    facture.extraction = {
        **extraction,
        "propositions_reponses": mapper_extraction_vers_reponses(facture.categorie_slug or "", extraction),
    }
    facture.statut = "analysee"
    facture.analysee_le = datetime.now(timezone.utc)
    await db.flush()
    return facture


async def appliquer(db: AsyncSession, session: SessionTrame, facture: SessionFacture, reponses: dict[str, Any]) -> None:
    """Applique les réponses confirmées/corrigées par le conseiller — jamais
    l'extraction brute directement (§3.1 : "conseiller valide/corrige avant
    de continuer")."""
    for question_id, valeur in reponses.items():
        await engine.enregistrer_reponse(db, session, question_id, valeur)
    facture.reponses_appliquees = reponses
    await db.flush()
