# ==============================================================================
#  IA_CONSEIL_WS — pub/sub Redis pour la mise à jour temps réel des sessions
#  de trame (WS /api/v1/sessions/{id}/live). PLAN_IMPLEMENTATION_4_PHASES.md
#  §0.5 : "Endpoint WebSocket avec Redis pub/sub pour la mise à jour temps
#  réel". Un canal par session — permet à plusieurs onglets/participants
#  (conseiller + lien client partagé, Phase 1 §1.5) de recevoir les mêmes
#  mises à jour sans repasser par une requête HTTP.
# ==============================================================================
import json
import logging
import uuid
from typing import Any

import redis.asyncio as redis

from backend.core.config import settings

logger = logging.getLogger(__name__)


def canal_session(session_id: uuid.UUID) -> str:
    return f"ia_conseil:session:{session_id}:live"


def _client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


async def publier(session_id: uuid.UUID, evenement: dict[str, Any]) -> None:
    """Best-effort : la mise à jour temps réel (WS /live) est un confort, pas
    une garantie — si Redis est indisponible (pas démarré en dev, coupure
    réseau...), on logue et on continue plutôt que de faire échouer toute la
    requête HTTP appelante (répondre à une question, finaliser une session...)
    qui n'a elle-même aucune dépendance fonctionnelle à Redis."""
    client = _client()
    try:
        await client.publish(canal_session(session_id), json.dumps(evenement, default=str))
    except redis.RedisError:
        logger.warning("Publication WS ia_conseil impossible (Redis indisponible) — session %s ignorée.", session_id)
    finally:
        await client.aclose()


def ouvrir_abonnement(session_id: uuid.UUID) -> tuple[redis.Redis, "redis.client.PubSub"]:
    client = _client()
    pubsub = client.pubsub()
    return client, pubsub
