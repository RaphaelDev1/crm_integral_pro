# ==============================================================================
#  ANALYSE FACTURE — extraction structurée (télécom/énergie) via Claude Haiku
#  vision, en remplacement du regex src/pdf_engine.py::analyser_facture
#  (~60% de précision). Même approche que backend/services/kyc_engine.py
#  (prompt système strict, parsing tolérant), avec ici des exemples few-shot
#  dans le prompt système pour stabiliser le format de sortie.
# ==============================================================================
from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

import anthropic

from backend.core.config import settings

logger = logging.getLogger(__name__)

MODEL_FACTURE_DEFAUT = "claude-haiku-4-5-20251001"

CHAMPS_FACTURE = (
    "operateur", "prix_ht", "prix_ttc", "data_conso_go", "options",
    "engagement_mois", "date_fin_engagement", "iban_prelevement",
)

SYSTEM_PROMPT_FACTURE = """Tu es un extracteur de données pour des factures françaises de télécom \
(mobile, box/fibre) et d'énergie (électricité, gaz), fournies en PDF (texte ou scan/image).

Réponds UNIQUEMENT avec un objet JSON valide (rien avant, rien après), avec exactement ces clés :
{"operateur": "", "prix_ht": 0.0, "prix_ttc": 0.0, "data_conso_go": 0.0, "options": [], \
"engagement_mois": 0, "date_fin_engagement": "", "iban_prelevement": ""}

Règles :
- operateur : nom de l'opérateur télécom ou du fournisseur d'énergie émetteur de la facture \
(Orange, SFR, Bouygues, Free, EDF, Engie, TotalEnergies, Ekwateur...)
- prix_ht / prix_ttc : montants hors taxes et toutes taxes comprises, nombres décimaux avec un \
point (0.0 si absent ou illisible)
- data_conso_go : quantité de data mobile en Go si applicable (forfait mobile), sinon 0.0
- options : liste des options/services inclus mentionnés (ex. "Appels illimités", "Assurance \
smartphone", "TV incluse", "Fibre 1Gb/s"), liste vide si aucune
- engagement_mois : durée d'engagement restante en mois, 0 si sans engagement ou introuvable
- date_fin_engagement : date de fin d'engagement au format "JJ/MM/AAAA", chaîne vide si absente
- iban_prelevement : IBAN utilisé pour le prélèvement s'il est visible sur le document, chaîne \
vide sinon
Si une information est absente ou illisible, utilise la valeur par défaut indiquée ci-dessus. \
Ne réponds rien d'autre que ce JSON.

Exemples :

Facture : Orange, forfait 5G 150 Go, prix HT 38,33 EUR, prix TTC 45,99 EUR, engagement 12 mois \
jusqu'au 15/03/2027, options "Appels illimités" et "Cloud 100 Go", prélèvement IBAN \
FR7630001007941234567890185.
JSON : {"operateur": "Orange", "prix_ht": 38.33, "prix_ttc": 45.99, "data_conso_go": 150.0, \
"options": ["Appels illimités", "Cloud 100 Go"], "engagement_mois": 12, \
"date_fin_engagement": "15/03/2027", "iban_prelevement": "FR7630001007941234567890185"}

Facture : EDF, abonnement + consommation électricité, montant TTC 89,00 EUR, sans engagement, \
aucun prélèvement automatique renseigné sur le document.
JSON : {"operateur": "EDF", "prix_ht": 0.0, "prix_ttc": 89.0, "data_conso_go": 0.0, \
"options": [], "engagement_mois": 0, "date_fin_engagement": "", "iban_prelevement": ""}
"""


class FactureAnalyzerError(Exception):
    """Échec de l'analyse facture (fichier introuvable/non PDF, clé API
    absente, appel ou réponse Claude inexploitables) — à l'appelant de
    décider du repli (nouvelle tentative, saisie manuelle...)."""


def _resultat_vide() -> dict:
    return {
        "operateur": "", "prix_ht": 0.0, "prix_ttc": 0.0, "data_conso_go": 0.0,
        "options": [], "engagement_mois": 0, "date_fin_engagement": "",
        "iban_prelevement": "",
    }


def _vers_float(valeur) -> float:
    if valeur in (None, ""):
        return 0.0
    try:
        return float(str(valeur).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return 0.0


def _vers_int(valeur) -> int:
    if valeur in (None, ""):
        return 0
    try:
        return int(float(str(valeur).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _normaliser(brut: dict) -> dict:
    res = _resultat_vide()
    if not isinstance(brut, dict):
        return res
    for champ in CHAMPS_FACTURE:
        if champ in brut and brut[champ] is not None:
            res[champ] = brut[champ]

    for champ in ("prix_ht", "prix_ttc", "data_conso_go"):
        res[champ] = _vers_float(res[champ])
    res["engagement_mois"] = _vers_int(res["engagement_mois"])

    if not isinstance(res["options"], list):
        res["options"] = []
    res["options"] = [str(o) for o in res["options"]]

    res["operateur"] = str(res["operateur"] or "")
    res["date_fin_engagement"] = str(res["date_fin_engagement"] or "")
    res["iban_prelevement"] = str(res["iban_prelevement"] or "")
    return res


def analyser_facture(
    chemin_pdf: str | Path, model: str = MODEL_FACTURE_DEFAUT, api_key: str | None = None
) -> dict:
    """Extrait les données structurées d'une facture PDF (télécom ou énergie,
    texte ou scan/image) via Claude Haiku vision. Retourne un dict avec les
    clés operateur, prix_ht, prix_ttc, data_conso_go, options,
    engagement_mois, date_fin_engagement, iban_prelevement.

    `api_key` permet à un appelant qui gère sa propre résolution de clé (ex.
    src/secrets_config.py côté Streamlit) de la fournir directement ; à
    défaut, repli sur `settings.anthropic_api_key` (backend/.env).

    Lève FactureAnalyzerError si le fichier est introuvable/vide/non PDF, si
    la clé API est absente, ou si l'appel/la réponse Claude sont
    inexploitables — jamais d'exception non gérée en cas d'échec réseau ou de
    réponse malformée."""
    chemin = Path(chemin_pdf)
    if chemin.suffix.lower() != ".pdf":
        raise FactureAnalyzerError(f"Format non supporté (PDF attendu) : {chemin}")
    if not chemin.is_file():
        raise FactureAnalyzerError(f"Fichier introuvable : {chemin}")
    cle = api_key or settings.anthropic_api_key

    contenu = chemin.read_bytes()
    if not contenu:
        raise FactureAnalyzerError(f"Fichier vide : {chemin}")

    if not cle:
        if settings.is_production:
            raise FactureAnalyzerError("ANTHROPIC_API_KEY absente (voir backend/.env.example).")
        logger.warning("ANTHROPIC_API_KEY absente — analyse facture simulée (dev) pour %s.", chemin)
        return _resultat_vide()

    b64 = base64.b64encode(contenu).decode("ascii")

    try:
        client = anthropic.Anthropic(api_key=cle)
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT_FACTURE,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}},
                    {"type": "text", "text": "Analyse cette facture et réponds avec le JSON attendu."},
                ],
            }],
        )
    except anthropic.APIError as exc:
        if settings.is_production:
            raise FactureAnalyzerError(f"Appel Claude échoué : {exc}") from exc
        logger.warning("Appel Claude échoué (%s) — analyse facture simulée (dev) pour %s.", exc, chemin)
        return _resultat_vide()

    texte = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    texte = re.sub(r"^```(?:json)?|```$", "", texte.strip(), flags=re.MULTILINE).strip()
    try:
        brut = json.loads(texte)
    except json.JSONDecodeError as exc:
        raise FactureAnalyzerError(f"Réponse Claude inexploitable : {exc}") from exc

    return _normaliser(brut)
