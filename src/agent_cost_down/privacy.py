import json
import os
import re
from typing import Any

KEY_PATTERN = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{12,}|gh[pousr]_[a-z0-9]{16,}|bearer\s+[a-z0-9._-]{12,}|ACD_SECRET_CANARY_[A-Z0-9_]+)"
)
DENIED = {"authorization", "api_key", "access_token", "cookie", "password", "database_url", "judge_code"}


def scrub(value: Any):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if k.lower() not in DENIED}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        for name in ("NEBIUS_API_KEY", "ACD_JUDGE_CODE", "ACD_CLIENT_SALT", "ACD_DATABASE_URL"):
            secret = os.getenv(name)
            if secret and len(secret) >= 8:
                value = value.replace(secret, "[REDACTED]")
        return KEY_PATTERN.sub("[REDACTED]", value)
    return value


def public_export(record: dict):
    clean = scrub(record)
    changed = clean != record
    if changed:
        # Do not silently turn private content into a publishable benchmark.
        raise ValueError("Publication blocked: a secret or forbidden field was detected")
    json.dumps(clean, allow_nan=False)
    return clean
