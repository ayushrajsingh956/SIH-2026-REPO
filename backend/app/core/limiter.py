from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# IP-based rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    enabled=settings.RATE_LIMITING_ENABLED,
)
