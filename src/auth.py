import logging
import os

from fastapi import Header

log = logging.getLogger(__name__)


async def optional_bearer_auth(authorization: str | None = Header(default=None)) -> bool:
    expected = os.getenv("API_KEY")
    if not expected:
        return False

    if not authorization:
        log.warning("request missing Authorization header (API_KEY is set) — allowing anyway")
        return False

    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == expected:
        return True

    log.warning("invalid bearer token — allowing anyway")
    return False
