"""Transport exceptions across the HTTP families supported by the SDK."""

import httpx

try:
    import httpx2
except ImportError:
    # Older Anthropic SDKs use httpx and do not install httpx2.
    _http_modules = (httpx,)
else:
    _http_modules = (httpx, httpx2)

HTTP_ERRORS = tuple(module.HTTPError for module in _http_modules)
RETRYABLE_STREAM_ERRORS = tuple(
    error
    for module in _http_modules
    for error in (module.ReadError, module.ReadTimeout, module.RemoteProtocolError)
)
