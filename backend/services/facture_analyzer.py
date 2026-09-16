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
from backend.services import storage_engine

logger = logging.getLogger(__name__)

MODEL_FACTURE_DEFAUT = "claude-haiku-4-5-20251001"

# Types réels acceptés (détectés par magic bytes, jamais par l'extension du
# nom de fichier — voir storage_engine.deviner_mime_reel). Le portail client
# accepte explicitement les photos de facture (.jpg/.jpeg/.png), donc
# l'analyse doit les supporter au même titre que le PDF.
MIME_AUTORISES_FACTURE = {"application/pdf", "image/jpeg", "image/png", "image/webp"}

CHAMPS_FACTURE = (
    "operateur", "prix_ht", "prix_ttc", "data_conso_go", "options",
    "engagement_mois", "date_fin_engagement", "iban_prelevement",
    "type_couverture", "bonus_malus",
)

SYSTEM_PROMPT_FACTURE = """Tu es un extracteur de données pour des factures/avis d'échéance français \
de télécom (mobile, box/fibre), d'énergie (électricité, gaz) et d'assurance auto, fournis en PDF \
(texte ou scan/image).

Réponds UNIQUEMENT avec un objet JSON valide (rien avant, rien après), avec exactement ces clés :
{"operateur": "", "prix_ht": 0.0, "prix_ttc": 0.0, "data_conso_go": 0.0, "options": [], \
"engagement_mois": 0, "date_fin_engagement": "", "iban_prelevement": "", "type_couverture": "", \
"bonus_malus": ""}

Règles :
- operateur : nom de l'opérateur télécom, du fournisseur d'énergie ou de l'assureur émetteur de \
la facture (Orange, SFR, Bouygues, Free, EDF, Engie, TotalEnergies, Ekwateur, MAIF, MAAF, Allianz...)
- prix_ht / prix_ttc : montants hors taxes et toutes taxes comprises, nombres décimaux avec un \
point (0.0 si absent ou illisible)
- data_conso_go : quantité de data mobile en Go si applicable (forfait mobile), sinon 0.0
- options : liste des options/services inclus mentionnés (ex. "Appels illimités", "Assurance \
smartphone", "TV incluse", "Fibre 1Gb/s"), liste vide si aucune
- engagement_mois : durée d'engagement restante en mois, 0 si sans engagement ou introuvable
- date_fin_engagement : date de fin d'engagement au format "JJ/MM/AAAA", chaîne vide si absente
- iban_prelevement : IBAN utilisé pour le prélèvement s'il est visible sur le document, chaîne \
vide sinon
- type_couverture : UNIQUEMENT pour une facture/avis d'échéance d'assurance auto — "Tiers", \
"Tiers étendu" ou "Tous risques" selon la formule souscrite, chaîne vide si le document n'est pas \
une assurance auto ou si l'information est introuvable
- bonus_malus : UNIQUEMENT pour une assurance auto — coefficient bonus-malus tel qu'affiché sur le \
document (ex. "0.85", "1.00", "1.25"), chaîne vide si non applicable ou introuvable
Si une information est totalement absente du document, utilise la valeur par défaut indiquée \
ci-dessus. Mais si elle est partiellement visible ou d'une lisibilité imparfaite (scan de mauvaise \
qualité, photo prise de travers, reflet, texte coupé...), donne ta meilleure estimation plutôt que \
de renvoyer une valeur vide — un résultat approximatif signalé comme tel est bien plus utile qu'une \
absence totale d'information, un conseiller humain vérifiera et corrigera ensuite. Ne réponds rien \
d'autre que ce JSON.

Exemples :

Facture : Orange, forfait 5G 150 Go, prix HT 38,33 EUR, prix TTC 45,99 EUR, engagement 12 mois \
jusqu'au 15/03/2027, options "Appels illimités" et "Cloud 100 Go", prélèvement IBAN \
FR7630001007941234567890185.
JSON : {"operateur": "Orange", "prix_ht": 38.33, "prix_ttc": 45.99, "data_conso_go": 150.0, \
"options": ["Appels illimités", "Cloud 100 Go"], "engagement_mois": 12, \
"date_fin_engagement": "15/03/2027", "iban_prelevement": "FR7630001007941234567890185", \
"type_couverture": "", "bonus_malus": ""}

Facture : EDF, abonnement + consommation électricité, montant TTC 89,00 EUR, sans engagement, \
aucun prélèvement automatique renseigné sur le document.
JSON : {"operateur": "EDF", "prix_ht": 0.0, "prix_ttc": 89.0, "data_conso_go": 0.0, \
"options": [], "engagement_mois": 0, "date_fin_engagement": "", "iban_prelevement": "", \
"type_couverture": "", "bonus_malus": ""}

Avis d'échéance : MAIF assurance auto, formule Tous risques, coefficient bonus-malus 0.85, \
cotisation annuelle TTC 620,00 EUR, prélèvement mensuel, sans engagement.
JSON : {"operateur": "MAIF", "prix_ht": 0.0, "prix_ttc": 620.0, "data_conso_go": 0.0, \
"options": [], "engagement_mois": 0, "date_fin_engagement": "", "iban_prelevement": "", \
"type_couverture": "Tous risques", "bonus_malus": "0.85"}
"""


class FactureAnalyzerError(Exception):
    """Échec de l'analyse facture (fichier introuvable/non PDF, clé API
    absente, appel ou réponse Claude inexploitables) — à l'appelant de
    décider du repli (nouvelle tentative, saisie manuelle...)."""


def _resultat_vide() -> dict:
    return {
        "operateur": "", "prix_ht": 0.0, "prix_ttc": 0.0, "data_conso_go": 0.0,
        "options": [], "engagement_mois": 0, "date_fin_engagement": "",
        "iban_prelevement": "", "type_couverture": "", "bonus_malus": "",
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
    res["type_couverture"] = str(res["type_couverture"] or "")
    res["bonus_malus"] = str(res["bonus_malus"] or "")
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

    Lève FactureAnalyzerError si le fichier est introuvable/vide/dans un
    format non supporté (PDF, JPG, PNG, WEBP — détecté par contenu réel, pas
    par l'extension), si la clé API est absente, ou si l'appel/la réponse
    Claude sont inexploitables — jamais d'exception non gérée en cas d'échec
    réseau ou de réponse malformée."""
    chemin = Path(chemin_pdf)
    if not chemin.is_file():
        raise FactureAnalyzerError(f"Fichier introuvable : {chemin}")

    contenu = chemin.read_bytes()
    if not contenu:
        raise FactureAnalyzerError(f"Fichier vide : {chemin}")

    mime_reel = storage_engine.deviner_mime_reel(contenu)
    if mime_reel not in MIME_AUTORISES_FACTURE:
        raise FactureAnalyzerError(
            f"Format non supporté (PDF, JPG, PNG ou WEBP attendu) : {chemin} (détecté : {mime_reel})"
        )

    cle = api_key or settings.anthropic_api_key

    if not cle:
        if settings.is_production:
            raise FactureAnalyzerError("ANTHROPIC_API_KEY absente (voir backend/.env.example).")
        logger.warning("ANTHROPIC_API_KEY absente — analyse facture simulée (dev) pour %s.", chemin)
        return _resultat_vide()

    b64 = base64.b64encode(contenu).decode("ascii")
    type_bloc = "document" if mime_reel == "application/pdf" else "image"
    bloc_fichier = {"type": type_bloc, "source": {"type": "base64", "media_type": mime_reel, "data": b64}}

    try:
        client = anthropic.Anthropic(api_key=cle)
        messages = [{
            "role": "user",
            "content": [bloc_fichier, {"type": "text", "text": "Analyse cette facture et réponds avec le JSON attendu."}],
        }]
        msg = client.messages.create(model=model, max_tokens=1024, system=SYSTEM_PROMPT_FACTURE, messages=messages)
        texte = _extraire_texte(msg)
        try:
            brut = json.loads(texte)
        except json.JSONDecodeError:
            # Une seule relance en cas de JSON légèrement malformé (prose
            # résiduelle, virgule en trop...) avant d'abandonner — évite de
            # perdre une extraction par ailleurs correcte pour un simple souci
            # de formatage de la réponse.
            messages += [
                {"role": "assistant", "content": texte},
                {"role": "user", "content": "Ta réponse n'est pas un JSON valide. Réponds UNIQUEMENT avec le JSON corrigé."},
            ]
            msg = client.messages.create(model=model, max_tokens=1024, system=SYSTEM_PROMPT_FACTURE, messages=messages)
            texte = _extraire_texte(msg)
            brut = json.loads(texte)
    except anthropic.APIError as exc:
        # Contrairement à la clé API absente (repli volontaire ci-dessus), un
        # échec d'appel Claude est une vraie anomalie (modèle invalide, requête
        # malformée, quota...) — l'avaler silencieusement en dev revenait à
        # renvoyer un résultat vide sans aucune trace exploitable, d'où
        # l'impression que l'analyse "ne détecte jamais rien" sans moyen de
        # savoir pourquoi. On la laisse toujours remonter.
        logger.exception("Appel Claude échoué pour %s.", chemin)
        raise FactureAnalyzerError(f"Appel Claude échoué : {exc}") from exc
    except json.JSONDecodeError as exc:
        raise FactureAnalyzerError(f"Réponse Claude inexploitable : {exc}") from exc

    resultat = _normaliser(brut)
    if resultat == _resultat_vide():
        logger.warning("Analyse facture : aucun champ détecté pour %s (document illisible ou hors périmètre).", chemin)
    return resultat


def _extraire_texte(msg) -> str:
    texte = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return re.sub(r"^```(?:json)?|```$", "", texte.strip(), flags=re.MULTILINE).strip()
