import hmac

from flask import current_app, request


def device_auth_error():
    expected = current_app.config.get("DEVICE_API_TOKEN", "")
    if not expected:
        return "Device API authentication is not configured", "DEVICE_AUTH_NOT_CONFIGURED", 503

    provided = request.headers.get("X-Device-Token", "")
    if not provided or not hmac.compare_digest(str(expected), provided):
        return "Unauthorized device", "DEVICE_UNAUTHORIZED", 401

    return None