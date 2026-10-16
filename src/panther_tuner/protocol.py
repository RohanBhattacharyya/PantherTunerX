"""Verified Phoenix wire framing and status checks, independent of HTTP and Qt."""

import base64
import json

from .models import DeviceError, TunerError


def encode_payload(payload: dict) -> tuple[bytes, dict[str, str]]:
    data = json.dumps(payload, allow_nan=False, separators=(",", ":")).encode("utf-8")
    return b"$@$" + base64.b64encode(data) + b"$@$", {
        "Content-Type": "application/octet-stream",
        "X-Decoded-Size": str(len(data)),
    }


def checked_response(action: str, result) -> dict:
    if not isinstance(result, dict) or not isinstance(result.get("GeneralReturn"), dict):
        raise TunerError(f"{action}: unrecognized diagnostics response")
    status = result["GeneralReturn"]
    if status.get("Error") != 0:
        raise DeviceError(action, status.get("Error"), status.get("ErrorMessage", "Unknown error"))
    return result
