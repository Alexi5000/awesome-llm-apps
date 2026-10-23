"""Caller admission for the plan trigger API.

Only the TripCraft Next.js server, which authenticates users and checks plan
ownership, may queue plan generation. It proves that with a shared secret in
the X-TripCraft-Internal-Token header. When no secret is configured (local
development), only loopback callers are admitted.
"""

import hmac
import ipaddress
import os
from typing import Optional

from fastapi import Header, HTTPException, Request, status

INTERNAL_TOKEN_ENV = "TRIPCRAFT_INTERNAL_API_TOKEN"


def _is_loopback(host: Optional[str]) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


async def require_internal_caller(
    request: Request,
    x_tripcraft_internal_token: Optional[str] = Header(default=None),
) -> None:
    expected = os.getenv(INTERNAL_TOKEN_ENV, "")
    if expected:
        supplied = x_tripcraft_internal_token or ""
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing internal API token",
            )
        return
    if not _is_loopback(request.client.host if request.client else None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Set {INTERNAL_TOKEN_ENV} to accept non-loopback callers",
        )
