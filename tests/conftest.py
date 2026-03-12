import json
import os
from typing import Any

import pytest
from dotenv import load_dotenv

from polytrader import PolyTrader

load_dotenv()

# Headers that contain sensitive data
_SENSITIVE_HEADERS = {
    "POLY_ADDRESS",
    "POLY_API_KEY",
    "POLY_PASSPHRASE",
    "POLY_SIGNATURE",
    "POLY_TIMESTAMP",
    "POLY_NONCE",
    "Cookie",
    "set-cookie",
}

# Keys to scrub from JSON response bodies (value must be valid for the field's format)
_SENSITIVE_BODY_REPLACEMENTS = {
    "apiKey": "FILTERED_apiKey",
    "secret": "RklMVEVSRURfc2VjcmV0",  # base64("FILTERED_secret") — must be valid base64
    "passphrase": "FILTERED_passphrase",
}


def _scrub_headers(headers: dict[str, Any]) -> dict[str, Any]:
    """Replace sensitive header values with placeholders."""
    for key in headers:
        if key in _SENSITIVE_HEADERS:
            headers[key] = [f"FILTERED_{key}"]
    return headers


def _scrub_response(response: dict[str, Any]) -> dict[str, Any]:
    """Scrub sensitive data from response headers and body."""
    _scrub_headers(response.get("headers", {}))

    body = response.get("body", {}).get("string", "")
    if not body:
        return response

    # Decode bytes to str for JSON parsing
    raw = body.decode("utf-8") if isinstance(body, bytes) else body

    try:
        data = json.loads(raw)
        if any(k in data for k in _SENSITIVE_BODY_REPLACEMENTS):
            for key, replacement in _SENSITIVE_BODY_REPLACEMENTS.items():
                if key in data:
                    data[key] = replacement
            scrubbed = json.dumps(data)
            # Preserve original type (bytes or str)
            response["body"]["string"] = (
                scrubbed.encode("utf-8") if isinstance(body, bytes) else scrubbed
            )
    except (json.JSONDecodeError, TypeError):
        pass

    return response


def _scrub_request(request: Any) -> Any:
    """Scrub sensitive data from request headers."""
    _scrub_headers(request.headers)
    return request


@pytest.fixture(scope="module")
def vcr_config() -> dict:
    """VCR config: decode gzip and scrub sensitive data."""
    return {
        "decode_compressed_response": True,
        "before_record_request": _scrub_request,
        "before_record_response": _scrub_response,
    }


@pytest.fixture
def trader() -> PolyTrader:
    """Create a PolyTrader instance from .env file."""
    private_key = os.environ["POLYMARKET_PRIVATE_KEY"]
    funder = os.environ["POLYMARKET_FUNDER"]
    signature_type = int(os.environ.get("POLYMARKET_SIGNATURE_TYPE", "0"))
    return PolyTrader(private_key, funder, signature_type)
