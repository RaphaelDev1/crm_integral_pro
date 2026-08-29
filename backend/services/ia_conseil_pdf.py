# ==============================================================================
#  IA_CONSEIL_PDF — synthèse PDF de fin de trame (§1.3). Réutilise la classe
#  PDFDemarche (fpdf2) de backend/services/document_engine.py plutôt que
#  Jinja2/weasyprint (non installés dans ce projet) — mêmes conventions que
#  les autres PDF du repo (mandat, résiliation...).
#
#  §3.3 — paragraphe de synthèse en langage naturel rédigé par Claude Haiku
#  (mêmes chiffres que le tableau comparatif, jamais recalculés/inventés par
#  le LLM — cf. RÈGLE ABSOLUE de audit_agent.py), mis en cache sur
#  SessionTrame.synthese_llm_texte après la première génération (idempotent,
#  un seul appel LLM par session).
# ==============================================================================
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.ia_conseil import ClientConseil, SessionTrame
from backend.models.user import User
from backend.services.document_engine import PDFDemarche, _txt

logger = logging.getLogger(__name__)

MODEL_SYNTHESE = "claude-haiku-4-5-20251001"

CATEGORIES_LABELS = {
    "mobile": "Mobile",
    "box": "Box Internet",
    "energie_elec": "Électricité",
    "energie_gaz": "Gaz",
}

SYSTEM_PROMPT_SYNTHESE = """Tu rédiges le paragraphe d'introduction personnalisé d'une synthèse \
PDF envoyée à un client par son conseiller IA Conseil (Mobile/Box/Énergie). On te donne un contexte \
JSON avec le prénom du client, la catégorie, l'offre recommandée et les chiffres déjà calculés \
(prix, économie mensuelle/annuelle, justifications).

RÈGLE ABSOLUE : n'invente et ne recalcule JAMAIS un chiffre — réutilise uniquement ceux fournis \
dans le contexte, tels quels. Ton rôle est uniquement la formulation, pas le calcul.

Écris UN SEUL paragraphe de 3 à 5 phrases, en français, ton professionnel et chaleureux, qui \
s'adresse directement au client (vouvoiement). Réponds uniquement avec le texte du paragraphe, \
sans titre ni guillemets."""


def _paragraphe_repli(client: ClientConseil, session: SessionTrame, recommandations: list[dict[str, Any]]) -> str:
    """Paragraphe simple sans LLM — utilisé si la clé API est absente ou
    l'appel échoue, pour ne jamais bloquer la génération du PDF."""
    prenom = client.prenom or ""
    salutation = f"Bonjour {prenom}," if prenom else "Bonjour,"
    categorie_label = CATEGORIES_LABELS.get(session.categorie_slug or "", session.categorie_slug or "")
    if not recommandations:
        return f"{salutation} voici la synthèse de notre échange concernant votre offre {categorie_label}."
    meilleure = recommandations[0]
    offre_nom = meilleure["offre"].nom
    eco = meilleure.get("economie_annuelle")
    phrase_eco = f" avec une économie estimée de {eco:.0f} EUR par an" if eco is not None and eco > 0 else ""
    return (
        f"{salutation} suite à notre échange, voici la synthèse de vos options {categorie_label}. "
        f"Notre recommandation principale est {offre_nom}{phrase_eco}."
    )


def _construire_contexte_synthese(
    client: ClientConseil, session: SessionTrame, recommandations: list[dict[str, Any]]
) -> dict[str, Any]:
    meilleure = recommandations[0] if recommandations else None
    offre = meilleure["offre"] if meilleure else None
    return {
        "client_prenom": client.prenom or "",
        "categorie": CATEGORIES_LABELS.get(session.categorie_slug or "", session.categorie_slug or ""),
        "offre_recommandee": offre.nom if offre else None,
        "prix_mensuel": float(offre.prix_mensuel) if offre and offre.prix_mensuel is not None else None,
        "economie_mensuelle": meilleure.get("economie_mensuelle") if meilleure else None,
        "economie_annuelle": meilleure.get("economie_annuelle") if meilleure else None,
        "justifications": (meilleure.get("justifications") or [])[:3] if meilleure else [],
    }


def generer_paragraphe_synthese(
    client: ClientConseil,
    session: SessionTrame,
    recommandations: list[dict[str, Any]],
    api_key: str | None = None,
    model: str = MODEL_SYNTHESE,
) -> str:
    cle = api_key or settings.anthropic_api_key
    if not cle:
        logger.warning("ANTHROPIC_API_KEY absente — paragraphe de synthèse en repli (dev/prod).")
        return _paragraphe_repli(client, session, recommandations)

    contexte = _construire_contexte_synthese(client, session, recommandations)
    try:
        anthropic_client = anthropic.Anthropic(api_key=cle)
        msg = anthropic_client.messages.create(
            model=model,
            max_tokens=400,
            system=SYSTEM_PROMPT_SYNTHESE,
            messages=[{"role": "user", "content": json.dumps(contexte, ensure_ascii=False)}],
        )
        texte = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
        if texte:
            return texte
    except anthropic.APIError:
        logger.exception("Échec de la génération du paragraphe de synthèse LLM.")

    return _paragraphe_repli(client, session, recommandations)


def _identite_client_conseil(client: ClientConseil) -> str:
    nom_complet = f"{client.prenom or ''} {client.nom or ''}".strip() or "Client"
    lignes = [nom_complet]
    if client.email:
        lignes.append(f"Email : {client.email}")
    if client.telephone:
        lignes.append(f"Tel : {client.telephone}")
    return "\n".join(lignes)


async def generer_pdf_synthese(
    db: AsyncSession,
    client: ClientConseil,
    session: SessionTrame,
    recommandations: list[dict[str, Any]],
    conseiller: User | None,
) -> bytes:
    """`recommandations` est la structure renvoyée par
    ia_conseil_engine.calculer_recommandations (liste de dicts avec `offre`
    ORM, `score`, `rang`, `justifications`, `alertes`, `economie_mensuelle`,
    `economie_annuelle`), déjà triée par score décroissant.

    Le paragraphe de synthèse LLM (§3.3) est généré une seule fois par
    session et mis en cache sur `session.synthese_llm_texte` — les appels
    suivants (PDF re-téléchargé) réutilisent le texte déjà généré plutôt que
    de refacturer un appel Claude."""
    if not session.synthese_llm_texte:
        session.synthese_llm_texte = generer_paragraphe_synthese(client, session, recommandations)
        await db.commit()

    categorie_label = CATEGORIES_LABELS.get(session.categorie_slug or "", session.categorie_slug or "")
    pdf = PDFDemarche(f"Synthese {categorie_label}")
    pdf.add_page()

    # ---- Page 1 : synthèse ----
    pdf.paragraphe(_identite_client_conseil(client), taille=10)
    pdf.ln(2)
    pdf.paragraphe(session.synthese_llm_texte, taille=10.5, espace_apres=2)

    meilleure = recommandations[0] if recommandations else None
    if meilleure and meilleure.get("economie_annuelle") is not None:
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(0, 150, 90)
        pdf.multi_cell(0, 8, _txt(f"Economie estimee : {meilleure['economie_annuelle']:.0f} EUR / an"))
        pdf.ln(4)
        pdf.set_text_color(35, 38, 45)

    pdf.paragraphe("Recommandations phares", taille=12, gras=True, espace_apres=2)
    for entree in recommandations[:3]:
        offre = entree["offre"]
        ligne = f"{entree['rang']}. {offre.nom} - {offre.prix_mensuel} EUR/mois (score {entree['score']:.0f}/100)"
        pdf.paragraphe(ligne, taille=10.5, espace_apres=1)
        for justification in entree.get("justifications", [])[:3]:
            pdf.paragraphe(f"   + {justification}", taille=9, espace_apres=0.5)
        for alerte in entree.get("alertes", []):
            pdf.paragraphe(f"   ! {alerte.get('message', '')}", taille=9, espace_apres=0.5)
        pdf.ln(2)

    # ---- Page 2 : détail comparatif ----
    pdf.add_page()
    pdf.paragraphe(f"Detail des offres comparees - {categorie_label}", taille=12, gras=True, espace_apres=3)
    for entree in recommandations:
        offre = entree["offre"]
        pdf.paragraphe(
            f"{entree['rang']}. {offre.nom} - {offre.prix_mensuel} EUR/mois "
            f"- engagement {offre.engagement_mois} mois - score {entree['score']:.0f}/100",
            taille=10,
            espace_apres=1.5,
        )

    # ---- Page finale : coordonnées conseiller ----
    pdf.add_page()
    pdf.paragraphe("Votre conseiller", taille=12, gras=True, espace_apres=3)
    if conseiller is not None:
        pdf.paragraphe(getattr(conseiller, "nom_complet", None) or "Conseiller IA Conseil", taille=10.5)
        if getattr(conseiller, "email", None):
            pdf.paragraphe(f"Email : {conseiller.email}", taille=10)
    pdf.champ_signature(label_droite="Signature du conseiller")

    return bytes(pdf.output())
