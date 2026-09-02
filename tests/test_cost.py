"""Provider-reported cost extraction and OpenRouter reconciliation tests."""

import httpx
import pytest

from nanopycodeagent.cost import (
    generation_url,
    pending_cost,
    resolve_generation_cost,
    usage_cost,
)


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://openrouter.ai/api", "https://openrouter.ai/api/v1/generation"),
        ("https://provider.example/api", "https://provider.example/api/v1/generation"),
        ("https://provider.example", "https://provider.example/v1/generation"),
        ("not a URL", None),
    ],
)
def test_generation_url_stays_on_the_configured_provider(base_url, expected):
    assert generation_url(base_url) == expected


def test_usage_cost_preserves_provider_reported_decimal():
    assert usage_cost({"input_tokens": 1, "output_tokens": 2, "cost": "0.00072"}) == {
        "status": "resolved",
        "amount": "0.00072",
        "currency": "USD",
        "source": "provider_response.usage.cost",
        "kind": "provider_reported",
    }
    assert pending_cost(None) == {"status": "unknown"}
    assert pending_cost("gen-1") == {
        "status": "pending",
        "source": "provider_generation",
    }


def test_generation_resolution_retries_until_cost_is_available():
    responses = iter(
        [
            httpx.Response(404, request=httpx.Request("GET", "https://provider.example/api/v1/generation")),
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://provider.example/api/v1/generation"),
                json={
                    "data": {
                        "total_cost": "0.00125",
                        "model": "anthropic/claude-sonnet-4",
                        "provider_name": "Anthropic",
                    }
                },
            ),
        ]
    )
    calls = []
    sleeps = []
    diagnostics = []

    def request(url, **kwargs):
        calls.append((url, kwargs))
        return next(responses)

    assert resolve_generation_cost(
        "https://provider.example/api",
        "gen-1", "secret", request=request, sleep=sleeps.append,
        diagnostics=diagnostics,
    ) == {
        "generation_id": "gen-1",
        "amount": "0.00125",
        "currency": "USD",
        "source": "provider_generation.total_cost",
        "model": "anthropic/claude-sonnet-4",
        "provider_name": "Anthropic",
    }
    assert len(calls) == 2
    assert calls[0][1]["headers"] == {"Authorization": "Bearer secret"}
    assert calls[0][1]["params"] == {"id": "gen-1"}
    assert sleeps == [1.0]
    assert diagnostics == [
        {"attempt": 1, "status": "http_error", "http_status": 404},
        {"attempt": 2, "status": "resolved", "http_status": 200},
    ]


def test_generation_resolution_failure_is_unknown_after_bounded_attempts():
    calls = []

    def request(*args, **kwargs):
        calls.append(None)
        raise httpx.ReadError("not ready")

    assert resolve_generation_cost(
        "https://provider.example/api",
        "gen-1", "secret", request=request, sleep=lambda _: None
    ) is None
    assert len(calls) == 6


def test_generation_resolution_does_not_retry_authentication_failure():
    diagnostics = []
    response = httpx.Response(
        401,
        request=httpx.Request("GET", "https://provider.example/api/v1/generation"),
    )

    assert resolve_generation_cost(
        "https://provider.example/api",
        "gen-1",
        "secret",
        request=lambda *args, **kwargs: response,
        sleep=lambda _: pytest.fail("must not retry a permanent failure"),
        diagnostics=diagnostics,
    ) is None
    assert diagnostics == [
        {"attempt": 1, "status": "http_error", "http_status": 401}
    ]


def test_generation_resolution_records_missing_cost_and_request_errors():
    responses = iter(
        [
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://provider.example/api/v1/generation"),
                json={"data": {}},
            ),
            httpx.ReadTimeout("not ready"),
        ]
    )
    diagnostics = []

    def request(*args, **kwargs):
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    assert resolve_generation_cost(
        "https://provider.example/api",
        "gen-1",
        "secret",
        attempts=2,
        request=request,
        sleep=lambda _: None,
        diagnostics=diagnostics,
    ) is None
    assert diagnostics == [
        {"attempt": 1, "status": "cost_unavailable", "http_status": 200},
        {"attempt": 2, "status": "request_error", "error_type": "ReadTimeout"},
    ]
