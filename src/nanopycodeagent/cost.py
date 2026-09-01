"""Resolve provider-reported costs for Anthropic-compatible model calls."""

from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

import httpx

from .event_journal import JsonObject

DEFAULT_ATTEMPTS = 6
DEFAULT_RETRY_DELAYS = (1.0, 2.0, 4.0, 8.0, 15.0)
RETRYABLE_HTTP_STATUSES = frozenset({404, 408, 409, 429, 500, 502, 503, 504})


def generation_url(base_url: object) -> str | None:
    """Build the provider-local generation endpoint from an SDK base URL."""
    try:
        parsed = urlsplit(str(base_url))
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    path = f"{parsed.path.rstrip('/')}/v1/generation"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def usage_cost(usage: JsonObject | None) -> JsonObject | None:
    """Return a resolved cost when the provider included one in usage."""
    if usage is None or "cost" not in usage:
        return None
    try:
        amount = Decimal(str(usage["cost"]))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return {
        "status": "resolved",
        "amount": str(amount),
        "currency": "USD",
        "source": "provider_response.usage.cost",
        "kind": "provider_reported",
    }


def pending_cost(generation_id: str | None) -> JsonObject:
    """Describe whether a model call can be reconciled later."""
    if generation_id is None:
        return {"status": "unknown"}
    return {"status": "pending", "source": "provider_generation"}


def resolve_generation_cost(
    base_url: object,
    generation_id: str,
    api_key: str,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    request: Callable[..., httpx.Response] = httpx.get,
    sleep: Callable[[float], None] = time.sleep,
    diagnostics: list[JsonObject] | None = None,
) -> JsonObject | None:
    """Query the configured provider's generation endpoint with bounded retry.

    Cost enrichment is best effort: transport errors, incomplete asynchronous
    records, and malformed responses all remain unknown to the caller.
    """
    endpoint = generation_url(base_url)
    if endpoint is None:
        if diagnostics is not None:
            diagnostics.append({"attempt": 0, "status": "unsupported_endpoint"})
        return None
    for attempt in range(attempts):
        try:
            response = request(
                endpoint,
                params={"id": generation_id},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            if response.status_code >= 400:
                if diagnostics is not None:
                    diagnostics.append(
                        {
                            "attempt": attempt + 1,
                            "status": "http_error",
                            "http_status": response.status_code,
                        }
                    )
                if response.status_code not in RETRYABLE_HTTP_STATUSES:
                    return None
                raise httpx.HTTPStatusError(
                    "retryable generation lookup response",
                    request=response.request,
                    response=response,
                )
            body = response.json()
            data = body.get("data") if isinstance(body, dict) else None
            if isinstance(data, dict) and data.get("total_cost") is not None:
                amount = Decimal(str(data["total_cost"]))
                if amount.is_finite() and amount >= 0:
                    result: JsonObject = {
                        "generation_id": generation_id,
                        "amount": str(amount),
                        "currency": "USD",
                        "source": "provider_generation.total_cost",
                    }
                    for source, target in (
                        ("model", "model"),
                        ("provider_name", "provider_name"),
                    ):
                        value = data.get(source)
                        if isinstance(value, str) and value:
                            result[target] = value
                    if diagnostics is not None:
                        diagnostics.append(
                            {
                                "attempt": attempt + 1,
                                "status": "resolved",
                                "http_status": response.status_code,
                            }
                        )
                    return result
            if diagnostics is not None:
                diagnostics.append(
                    {
                        "attempt": attempt + 1,
                        "status": "cost_unavailable",
                        "http_status": response.status_code,
                    }
                )
        except httpx.HTTPStatusError:
            # Retryable HTTP failures were recorded before raising.
            pass
        except Exception as exc:
            # Enrichment must never replace the agent's real task outcome.
            if diagnostics is not None:
                diagnostics.append(
                    {
                        "attempt": attempt + 1,
                        "status": "request_error",
                        "error_type": type(exc).__name__,
                    }
                )
        if attempt < attempts - 1:
            sleep(DEFAULT_RETRY_DELAYS[min(attempt, len(DEFAULT_RETRY_DELAYS) - 1)])
    return None
