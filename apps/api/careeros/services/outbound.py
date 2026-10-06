"""Bounded provider retries; only repeat ambiguous POSTs with an idempotency key."""

import asyncio
import logging
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger("careeros.providers")


async def post_json(client, url, *, headers, payload):
    for attempt in range(3):
        try:
            response = await client.post(
                url, headers={"User-Agent": "CareerOS/1.0", **headers}, json=payload
            )
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            retryable = code == 429 or (
                "Idempotency-Key" in headers and (code is None or code in (500, 502, 503, 504))
            )
            logger.warning(
                "provider_request_failed",
                extra={
                    "host": urlsplit(url).hostname,
                    "attempt": attempt + 1,
                    "error_type": type(exc).__name__,
                },
            )
            if attempt == 2 or not retryable:
                raise
            await asyncio.sleep(2**attempt)
