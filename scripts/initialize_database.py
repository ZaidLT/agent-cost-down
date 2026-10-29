"""Explicit deployment schema setup. Never enables funding or prints connection secrets."""

import hashlib
import json
import os
from urllib.parse import urlsplit

from sqlalchemy import inspect, text

from agent_cost_down.api import hosted_database_url
from agent_cost_down.ledger import Ledger


def main():
    database = None
    try:
        url = hosted_database_url()
        parsed = urlsplit(url)
        if parsed.scheme not in {"postgres", "postgresql", "postgresql+psycopg"}:
            raise ValueError("A PostgreSQL integration URL is required")
        identity = hashlib.sha256(((parsed.hostname or "") + parsed.path).encode()).hexdigest()[:16]
        if os.getenv("VERCEL_ENV") == "preview":
            production = os.getenv("ACD_PRODUCTION_DATABASE_FINGERPRINT")
            if not production or identity == production:
                raise ValueError("Preview database isolation must be verified before schema changes")
        database = Ledger(url)
        with database.engine.connect() as connection:
            assert connection.execute(text("select 1")).scalar() == 1
        database.initialize_schema()
        print(
            json.dumps(
                {
                    "database_setup": "ok",
                    "environment": os.getenv("VERCEL_ENV", "local"),
                    "database_fingerprint": identity,
                    "pooled": "-pooler" in (parsed.hostname or ""),
                    "tables": inspect(database.engine).get_table_names(),
                    "funding_configured": bool(database.ready()),
                }
            )
        )
    except Exception as exc:  # noqa: BLE001 - raw connection errors can reveal private connection details
        print(json.dumps({"database_setup": "failed", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None
    finally:
        if database:
            database.engine.dispose()


if __name__ == "__main__":
    main()
