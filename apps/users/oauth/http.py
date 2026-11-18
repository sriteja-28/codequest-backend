"""
Minimal JSON-over-HTTPS client for talking to the OAuth providers.

Standard library only (urllib + the system CA store), short timeouts, capped
response size. Providers receive an instance, so tests inject a fake.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

MAX_BODY_BYTES = 1_000_000
USER_AGENT = "CodeQuest-OAuth/1.0"


class ProviderError(Exception):
    """Sign-in could not be completed with the provider. `code` is shown to the user as a reason."""

    def __init__(self, code: str = "provider_error", detail: str = ""):
        super().__init__(detail or code)
        self.code = code


class OAuthHTTP:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def post_form(self, url: str, data: dict, headers: dict | None = None):
        body = urllib.parse.urlencode(data).encode()
        request = urllib.request.Request(url, data=body, method="POST", headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            **(headers or {}),
        })
        return self._send(request)

    def get_json(self, url: str, headers: dict | None = None):
        request = urllib.request.Request(url, method="GET", headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            **(headers or {}),
        })
        return self._send(request)

    def _send(self, request):
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_BODY_BYTES)
        except urllib.error.HTTPError as exc:
            raise ProviderError("provider_rejected", f"HTTP {exc.code} from {request.full_url}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError("provider_unreachable", str(exc)) from None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ProviderError("provider_bad_response", f"non-JSON reply from {request.full_url}") from None
