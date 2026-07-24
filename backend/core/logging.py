# ==============================================================================
#  LOGGING STRUCTURÉ — un log JSON par ligne sur stdout (au lieu du format
#  texte par défaut) pour être exploitable par n'importe quel agrégateur de
#  logs (Fly.io, Railway, etc. les capturent tous depuis stdout). Appelé une
#  fois au chargement de backend/main.py (process API) et de
#  backend/workers/celery_app.py (process worker/beat — ne partage pas le
#  logging de l'API).
# ==============================================================================
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from backend.core.config import settings

_CHAMPS_RESERVES = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message"}


class _FormatteurJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Champs additionnels passés via logger.info(..., extra={...})
        for cle, valeur in record.__dict__.items():
            if cle not in _CHAMPS_RESERVES:
                payload[cle] = valeur
        return json.dumps(payload, ensure_ascii=False, default=str)


_configure = False


def configurer_logging() -> None:
    """Idempotent : peut être appelée plusieurs fois (import multiple) sans
    dupliquer les handlers."""
    global _configure
    if _configure:
        return
    _configure = True

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_FormatteurJSON())

    racine = logging.getLogger()
    racine.handlers = [handler]
    racine.setLevel(logging.INFO if settings.is_production else logging.DEBUG)

    # Bruit habituel des libs tierces, sans le supprimer complètement.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
