import json
from typing import Any


class ParseFailure(ValueError):
    pass


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ParseFailure("Duplicate JSON key")
        result[key] = value
    return result


def parse_arguments(raw: str) -> tuple[dict[str, Any], bool]:
    if not isinstance(raw, str) or len(raw.encode()) > 16384:
        raise ParseFailure("Arguments must be a bounded string")
    clean = raw.strip().removeprefix("\ufeff").strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        if len(lines) < 3 or lines[0].lower() not in {"```", "```json"} or lines[-1] != "```":
            raise ParseFailure("Invalid enclosing code fence")
        clean = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(
            clean,
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ParseFailure("Non-finite JSON")),
        )
    except (ValueError, TypeError, RecursionError) as exc:
        raise ParseFailure("Invalid JSON object") from exc
    if not isinstance(value, dict):
        raise ParseFailure("Tool arguments must be an object")
    return value, clean != raw
