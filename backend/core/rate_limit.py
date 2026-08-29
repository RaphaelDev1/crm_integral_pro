# ==============================================================================
#  RATE LIMITING — instance slowapi partagée (P3.1). Module séparé pour éviter
#  tout import circulaire entre backend/main.py (montage de l'exception
#  handler) et les routers qui décorent leurs endpoints avec @limiter.limit(...)
#  (ex. backend/routers/leads_public.py).
#
#  Stockage : settings.rate_limit_storage_uri — "memory://" par défaut (dev,
#  tests, un seul process), à basculer sur Redis en prod multi-instances.
# ==============================================================================
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.core.config import settings

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.rate_limit_storage_uri)
