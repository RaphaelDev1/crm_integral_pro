# ==============================================================================
#  VALIDATION KYC — CNI, justificatif de domicile (< 3 mois), RIB, via Claude
#  Haiku vision (coût cible ~0,002 € / document). Même approche que
#  src/pdf_engine.py::analyser_facture_vision (prompt JSON strict, parsing
#  tolérant).
# ==============================================================================
from __future__ import annotations

import base64
import json
import logging
import re

import anthropic

from backend.core.config import settings

logger = logging.getLogger(__name__)

MODEL_KYC_DEFAUT = "claude-haiku-4-5-20251001"

TYPES_DOCUMENT = ("cni", "justificatif_domicile", "rib", "autre")

_MIME_PAR_EXTENSION = {
    "pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
}

PROMPT_KYC = (
    "Tu es un contrôleur KYC pour un mandataire multi-univers (télécom, énergie). "
    "Ce document est-il une CNI valide, un justificatif de domicile de moins de "
    "3 mois, ou un RIB ? Réponds UNIQUEMENT avec un objet JSON valide (rien avant, "
    "rien après), avec exactement ces clés :\n"
    '{"type": "cni|justificatif_domicile|rib|autre", "valide": true|false, "motif_rejet": ""}\n\n'
    "Règles :\n"
    "- type : nature réelle du document, même s'il est invalide\n"
    "- valide : true seulement si le document est lisible, complet, non expiré "
    "(CNI), daté de moins de 3 mois (justificatif de domicile), ou cohérent avec "
    "un IBAN lisible (RIB)\n"
    "- motif_rejet : raison courte et précise si valide=false (ex. \"CNI expirée "
    "le 01/2024\", \"document illisible\", \"facture de plus de 3 mois\"), chaîne "
    "vide si valide=true\n"
    "Ne réponds rien d'autre que ce JSON."
)


class KycError(Exception):
    """Échec de l'analyse KYC (clé API absente, format non supporté, appel ou
    réponse Claude inexploitables) — à l'appelant de décider du repli (relance
    manuelle, nouvelle tentative Celery...)."""


def _resultat_kyc_simule(nom_fichier: str) -> dict:
    """Résultat de secours utilisé en dev quand Claude est inaccessible (clé
    absente ou crédit API épuisé) — permet de tester le flux d'upload/KYC de
    bout en bout sans consommer de crédit Anthropic. Ne fait aucune vraie
    vérification : jamais utilisé en production, voir valider_document."""
    nom = nom_fichier.lower()
    if "cni" in nom or "identite" in nom or "carte" in nom:
        type_doc = "cni"
    elif "rib" in nom or "iban" in nom:
        type_doc = "rib"
    elif "justif" in nom or "domicile" in nom or "facture" in nom:
        type_doc = "justificatif_domicile"
    else:
        type_doc = "autre"
    return {"type": type_doc, "valide": True, "motif_rejet": ""}


def valider_document(contenu: bytes, nom_fichier: str, model: str = MODEL_KYC_DEFAUT) -> dict:
    """Valide un document KYC (CNI, justificatif de domicile ou RIB — PDF, JPG
    ou PNG) via Claude Haiku vision. Retourne {type, valide, motif_rejet}."""
    if not contenu:
        raise KycError("Document vide.")

    ext = nom_fichier.rsplit(".", 1)[-1].lower() if "." in nom_fichier else ""
    mime = _MIME_PAR_EXTENSION.get(ext)
    if not mime:
        raise KycError(f"Format non supporté : .{ext or '?'} (attendu pdf/jpg/jpeg/png).")

    if not settings.anthropic_api_key:
        if settings.is_production:
            raise KycError("ANTHROPIC_API_KEY absente (voir backend/.env.example).")
        logger.warning("ANTHROPIC_API_KEY absente — validation KYC simulée (dev) pour %s.", nom_fichier)
        return _resultat_kyc_simule(nom_fichier)

    bloc_type = "document" if mime == "application/pdf" else "image"
    b64 = base64.b64encode(contenu).decode("ascii")

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {"type": bloc_type, "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {"type": "text", "text": PROMPT_KYC},
                ],
            }],
        )
    except anthropic.APIError as exc:
        if settings.is_production:
            raise KycError(f"Appel Claude échoué : {exc}") from exc
        logger.warning("Appel Claude échoué (%s) — validation KYC simulée (dev) pour %s.", exc, nom_fichier)
        return _resultat_kyc_simule(nom_fichier)

    try:
        texte = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        texte = re.sub(r"^```(?:json)?|```$", "", texte.strip(), flags=re.MULTILINE).strip()
        brut = json.loads(texte)
    except (json.JSONDecodeError, ValueError) as exc:
        raise KycError(f"Réponse Claude inexploitable : {exc}") from exc

    type_doc = brut.get("type") if brut.get("type") in TYPES_DOCUMENT else "autre"
    return {
        "type": type_doc,
        "valide": bool(brut.get("valide", False)),
        "motif_rejet": str(brut.get("motif_rejet") or ""),
    }
