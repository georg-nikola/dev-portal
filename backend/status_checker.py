from __future__ import annotations

import httpx

from config import settings


async def ping_url(url: str) -> str:
    """Ping a URL and return a status string.

    Does NOT follow redirects so that services behind Cloudflare Access
    (which return 302 to a login page) are not falsely reported as healthy.
    """
    try:
        async with httpx.AsyncClient(
            timeout=settings.status_check_timeout,
            follow_redirects=False,
        ) as client:
            response = await client.get(url)
        if response.status_code < 300:
            return "healthy"
        if response.status_code < 400:
            return "unknown"
        return "degraded"
    except httpx.TimeoutException:
        return "down"
    except Exception:
        return "down"
