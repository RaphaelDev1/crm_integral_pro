# ==============================================================================
#  COPILOT_ENGINE — copilote conseiller en temps réel pendant une session de
#  trame (§3.2). Streaming SSE (client.messages.stream), 3 modes :
#  suggestion de question, détection d'incohérence, aide à la reformulation.
#  Prompts versionnés dans backend/prompts/copilot/*.md.
# ==============================================================================
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterator

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.ia_conseil import SessionTrame
from backend.services import ia_conseil_engine as engine

logger = logging.getLogger(__name__)

MODEL_COPILOT = "claude-sonnet-5"
MODES = ("suggestion", "incoherence", "reformulation")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "copilot"


def _charger_prompt(mode: str) -> str:
    return (_PROMPTS_DIR / f"{mode}.md").read_text(encoding="utf-8")


PROMPTS = {mode: _charger_prompt(mode) for mode in MODES}


class ModeInvalideError(Exception):
    def __init__(self, mode: str):
        super().__init__(f"Mode copilote inconnu : {mode!r} (attendu : {', '.join(MODES)}).")
        self.mode = mode


async def construire_contexte(db: AsyncSession, session: SessionTrame) -> dict[str, Any]:
    """Contexte envoyé au LLM : réponses déjà collectées + top offres
    candidates (déjà scorées par le moteur de règles, jamais recalculées par
    le LLM lui-même)."""
    recommandations = await engine.calculer_recommandations(db, session)
    return {
        "categorie": session.categorie_slug,
        "reponses": session.reponses or {},
        "offres_candidates": [
            {
                "nom": r["offre"].nom,
                "prix_mensuel": float(r["offre"].prix_mensuel) if r["offre"].prix_mensuel is not None else None,
                "score": r["score"],
            }
            for r in recommandations[:5]
        ],
    }


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_copilot(
    mode: str, contexte: dict[str, Any], message: str | None = None,
    api_key: str | None = None, model: str = MODEL_COPILOT,
) -> Iterator[str]:
    """Générateur synchrone de deltas de texte au format SSE. Starlette
    exécute automatiquement un itérateur non-async dans un threadpool
    (StreamingResponse.body_iterator), pas besoin d'`async for` ici — même
    logique bloquante déjà acceptée ailleurs dans ce repo pour les appels
    Claude synchrones (facture_analyzer.py, audit_agent.py)."""
    if mode not in MODES:
        raise ModeInvalideError(mode)

    cle = api_key or settings.anthropic_api_key
    if not cle:
        logger.warning("ANTHROPIC_API_KEY absente — copilote indisponible (dev/prod).")
        yield _sse("error", {"detail": "Copilote non configuré (clé API Anthropic manquante)."})
        return

    contenu_utilisateur = json.dumps(
        {"contexte": contexte, "question_conseiller": message or ""}, ensure_ascii=False
    )
    try:
        client = anthropic.Anthropic(api_key=cle)
        with client.messages.stream(
            model=model, max_tokens=500, system=PROMPTS[mode],
            messages=[{"role": "user", "content": contenu_utilisateur}],
        ) as stream:
            for texte in stream.text_stream:
                yield _sse("delta", {"text": texte})
        yield _sse("done", {})
    except anthropic.APIError as exc:
        logger.exception("Échec du copilote conseiller (mode=%s).", mode)
        yield _sse("error", {"detail": f"Erreur copilote : {exc}"})
