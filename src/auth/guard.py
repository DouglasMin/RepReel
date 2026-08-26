import os
from typing import Dict, Any, Tuple, Optional


def verify_request_authorization(headers: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Verifies that the incoming request is authorized.
    Supports:
      1. x-app-secret / X-App-Secret header (Secret known only by the authorized iOS app client)
      2. User Whitelist checking (x-user-id / x-user-email against ALLOWED_USER_EMAILS)
    """
    # Normalize headers to lowercase
    normalized_headers = {k.lower(): v for k, v in (headers or {}).items()}

    configured_app_secret = os.getenv("APP_SECRET_KEY")
    allowed_emails = [
        email.strip().lower()
        for email in os.getenv("ALLOWED_USER_EMAILS", "").split(",")
        if email.strip()
    ]

    # 1. Check App Secret Key (if configured)
    provided_secret = (
        normalized_headers.get("x-app-secret")
        or normalized_headers.get("authorization", "").replace("Bearer ", "").strip()
    )

    if configured_app_secret:
        if not provided_secret or provided_secret != configured_app_secret:
            return False, "Invalid or missing app authorization token (x-app-secret)."

    # 2. Check User Allowlist (if configured)
    user_email = (
        normalized_headers.get("x-user-email")
        or normalized_headers.get("x-user-id")
    )

    if allowed_emails:
        if not user_email or (user_email.strip().lower() not in allowed_emails):
            return False, f"Access denied. '{user_email or 'Anonymous'}' is not in the authorized user whitelist."

    return True, None
