from __future__ import annotations

import math
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field, model_validator
from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    select,
    update,
)
from sqlalchemy.pool import NullPool, StaticPool

from .contracts import Contract

NANO = 1_000_000_000
metadata = MetaData()
settings = Table(
    "settings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("allocations", JSON, nullable=False),
    Column("expires", String, nullable=False),
    Column("enabled", Integer, nullable=False),
)
jobs = Table(
    "jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("dedupe", String, unique=True, nullable=False),
    Column("client", String, nullable=False),
    Column("pool", String, nullable=False),
    Column("task_id", String, nullable=False),
    Column("policy_id", String, nullable=False),
    Column("status", String, nullable=False),
    Column("created", Float, nullable=False),
    Column("lease_until", Float),
    Column("owner", String),
    Column("reserved", BigInteger, nullable=False),
    Column("charged", BigInteger, nullable=False),
    Column("result", JSON),
    Column("error", String),
    Column("payload_hash", String, nullable=False),
)
events = Table(
    "usage_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String, nullable=False),
    Column("status", String, nullable=False),
    Column("cost", BigInteger),
    Column("data", JSON),
    Column("created", Float, nullable=False),
)

dispatches = Table(
    "queue_dispatches",
    metadata,
    Column("run_id", String, primary_key=True),
    Column("status", String, nullable=False),
    Column("updated", Float, nullable=False),
)
rate_history = Table(
    "provider_rate_history",
    metadata,
    Column("id", String, primary_key=True),
    Column("created", Float, nullable=False),
    Column("tokens", BigInteger, nullable=False),
)


class Denied(ValueError):
    pass


class Credits(Contract):
    confirmed_at: str
    expires_at: str | None
    no_expiry_confirmed: bool = False
    usable_usd_after_liabilities: float = Field(gt=0)
    promotional_only: bool
    billing_overage_acknowledged: bool
    # Legacy evidence only: disabling optional top-ups does not prevent automatic billing.
    topups_disabled: bool | None = None
    evidence_reference: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid(self):
        if not (self.promotional_only and self.billing_overage_acknowledged):
            raise ValueError("Confirmed promotional funding and billing-risk acknowledgement are required")
        if self.expires_at is None and not self.no_expiry_confirmed:
            raise ValueError("Missing expiry requires explicit no-expiry confirmation")
        if self.expires_at is not None and self.no_expiry_confirmed:
            raise ValueError("Specify an expiry date or confirmed no expiry, not both")
        for field in (self.confirmed_at, self.expires_at):
            if field is not None and datetime.fromisoformat(field).tzinfo is None:
                raise ValueError("Credit timestamps require a timezone")
        if self.expires_at is not None and datetime.fromisoformat(self.expires_at) <= datetime.now(UTC):
            raise ValueError("Credits have expired")
        return self


def nanos(usd):
    if not math.isfinite(usd) or usd < 0:
        raise ValueError("Invalid amount")
    return math.ceil(usd * NANO)


class Ledger:
    def __init__(self, url):
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        opts = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            opts["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if ":memory:" in url:
                opts["poolclass"] = StaticPool
            elif "///" in url:
                Path(url.split("///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)
        else:
            # Neon supplies the external pool; do not multiply persistent connections per function.
            opts["poolclass"] = NullPool
        self.engine = create_engine(url, **opts)

    def initialize_schema(self):
        """Explicit deployment/CLI operation, never called from a request or worker startup."""
        metadata.create_all(self.engine)

    def rate_delay(self, tokens, rpm, tpm):
        if rpm < 1 or tpm < 1 or tokens < 0:
            raise ValueError("Rate limits must be positive and tokens nonnegative")
        if tokens > tpm:
            raise Denied("One bounded request exceeds the provider token allowance")
        with self.transaction() as con:
            self._config(con)
            stamp = time.time()
            con.execute(rate_history.delete().where(rate_history.c.created <= stamp - 60))
            recent = list(con.execute(select(rate_history).order_by(rate_history.c.created)).mappings())
            if len(recent) < rpm and sum(r["tokens"] for r in recent) + tokens <= tpm:
                con.execute(rate_history.insert().values(id=str(uuid.uuid4()), created=stamp, tokens=tokens))
                return 0.0
            return max(0.01, recent[0]["created"] + 60 - stamp)

    def begin_dispatch(self, run_id):
        with self.transaction() as con:
            row = con.execute(select(jobs).where(jobs.c.id == run_id)).mappings().one()
            previous = con.execute(select(dispatches).where(dispatches.c.run_id == run_id)).first()
            if row["status"] != "queued" or previous:
                return False
            con.execute(dispatches.insert().values(run_id=run_id, status="sending", updated=time.time()))
            return True

    def sent_dispatch(self, run_id):
        with self.transaction() as con:
            con.execute(
                update(dispatches)
                .where(dispatches.c.run_id == run_id)
                .values(status="sent", updated=time.time())
            )

    def fail_dispatch(self, run_id):
        """Cancel only unclaimed work, including a send whose acknowledgement was lost."""
        with self.transaction() as con:
            row = con.execute(select(jobs).where(jobs.c.id == run_id)).mappings().one()
            if row["status"] == "queued":
                con.execute(
                    update(jobs)
                    .where(jobs.c.id == run_id)
                    .values(
                        status="failed", reserved=0, error="Queue dispatch failed. No model call was started."
                    )
                )
                con.execute(
                    update(dispatches)
                    .where(dispatches.c.run_id == run_id)
                    .values(status="failed", updated=time.time())
                )

    def recover_queue(self):
        """Bound abandoned dispatches and leases without replaying uncertain model calls."""
        with self.transaction() as con:
            stamp = time.time()
            rows = list(con.execute(select(jobs).where(jobs.c.pool.in_(["public", "judge"]))).mappings())
            for row in rows:
                if row["status"] == "running" and row["lease_until"] <= stamp:
                    con.execute(
                        update(jobs)
                        .where(jobs.c.id == row["id"])
                        .values(
                            status="interrupted",
                            lease_until=None,
                            error="Worker interrupted; uncertain requests will not be replayed",
                        )
                    )
                if row["status"] != "queued":
                    continue
                dispatch = (
                    con.execute(select(dispatches).where(dispatches.c.run_id == row["id"])).mappings().first()
                )
                timeout = 120 if not dispatch or dispatch["status"] == "sending" else 900
                if row["created"] < stamp - timeout:
                    con.execute(
                        update(jobs)
                        .where(jobs.c.id == row["id"])
                        .values(status="failed", reserved=0, error="Queue delivery expired before execution.")
                    )

    @contextmanager
    def transaction(self):
        with self.engine.connect() as con:
            if self.engine.dialect.name == "sqlite":
                con.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                con.begin()
                # One transaction-level lock serializes quota, reservation, and claim decisions.
                con.exec_driver_sql("SELECT pg_advisory_xact_lock(728450121)")
            try:
                yield con
                con.commit()
            except BaseException:
                con.rollback()
                raise

    def configure(self, credits: Credits):
        total = nanos(credits.usable_usd_after_liabilities)
        allocations = {
            k: int(total * share)
            for k, share in {"development": 0.10, "evaluation": 0.50, "judge": 0.20, "public": 0.10}.items()
        }
        # A judge reserve must remain funded throughout the promised access period.
        if credits.expires_at is not None and datetime.fromisoformat(credits.expires_at) < datetime(
            2026, 12, 16, tzinfo=UTC
        ):
            allocations["judge"] = 0
        with self.transaction() as con:
            if con.execute(select(settings)).first():
                raise Denied(
                    "Ledger already configured; reconcile existing liabilities before changing funding"
                )
            con.execute(
                settings.insert().values(
                    id=1, allocations=allocations, expires=credits.expires_at or "no_expiry", enabled=1
                )
            )

    def ready(self):
        with self.engine.connect() as con:
            return con.execute(select(settings)).mappings().first()

    def remaining(self, pool):
        with self.transaction() as con:
            config = self._config(con)
            rows = con.execute(select(jobs).where(jobs.c.pool == pool)).mappings()
            return (
                config["allocations"].get(pool, 0) - sum(r["reserved"] + r["charged"] for r in rows)
            ) / NANO

    def active_lease_delay(self):
        with self.engine.connect() as con:
            leases = list(con.execute(select(jobs.c.lease_until).where(jobs.c.status == "running")).scalars())
            return max(0, min(leases) - time.time()) if leases else None

    def _config(self, con):
        config = con.execute(select(settings)).mappings().first()
        if not config or not config["enabled"]:
            raise Denied("Live spending is disabled")
        if config["expires"] != "no_expiry" and datetime.fromisoformat(config["expires"]) <= datetime.now(
            UTC
        ):
            raise Denied("Confirmed credits expired")
        return config

    def submit(self, *, task_id, policy_id, client, key, pool, reserve, payload_hash, hosted=True):
        if pool not in {"public", "judge", "development", "evaluation"}:
            raise Denied("Unknown credit allocation")
        dedupe = pool + ":" + client + ":" + key
        with self.transaction() as con:
            previous = con.execute(select(jobs).where(jobs.c.dedupe == dedupe)).mappings().first()
            if previous:
                if previous["payload_hash"] != payload_hash:
                    raise Denied("Idempotency key already used for another request")
                return dict(previous)
            config = self._config(con)
            existing = list(con.execute(select(jobs)).mappings())
            stamp = time.time()
            if hosted:
                active = [
                    j
                    for j in existing
                    if j["status"] in {"queued", "running"} and j["pool"] in {"public", "judge"}
                ]
                if len(active) >= 3:
                    raise Denied("Queue is full")
                if pool == "public":
                    recent = [j for j in existing if j["client"] == client and j["pool"] == pool]
                    if (
                        sum(j["created"] > stamp - 3600 for j in recent) >= 2
                        or sum(j["created"] > stamp - 86400 for j in recent) >= 20
                    ):
                        raise Denied("Public quota exhausted")
            committed = sum(j["reserved"] + j["charged"] for j in existing if j["pool"] == pool)
            amount = nanos(reserve)
            if committed + amount > config["allocations"].get(pool, 0):
                raise Denied("Credit allocation cannot cover the worst-case reservation")
            row = {
                "id": str(uuid.uuid4()),
                "dedupe": dedupe,
                "client": client,
                "pool": pool,
                "task_id": task_id,
                "policy_id": policy_id,
                "status": "queued",
                "created": stamp,
                "lease_until": None,
                "owner": None,
                "reserved": amount,
                "charged": 0,
                "result": None,
                "error": None,
                "payload_hash": payload_hash,
            }
            con.execute(jobs.insert().values(**row))
            return row

    def claim(self, owner, lease_seconds=660, run_id=None, hosted=False, max_active=1):
        if max_active not in {1, 2} or (hosted and max_active != 1):
            raise ValueError("Hosted concurrency is one; local pilots permit at most two")
        with self.transaction() as con:
            self._config(con)
            running = list(con.execute(select(jobs).where(jobs.c.status == "running")).mappings())
            active = [row for row in running if row["lease_until"] > time.time()]
            for row in running:
                if row in active:
                    continue
                con.execute(
                    update(jobs)
                    .where(jobs.c.id == row["id"])
                    .values(
                        status="interrupted",
                        error="Worker interrupted; uncertain requests will not be replayed",
                    )
                )
            if len(active) >= max_active:
                return None
            queued = list(con.execute(select(jobs).where(jobs.c.status == "queued")).mappings())
            if hosted:
                queued = [j for j in queued if j["pool"] in {"judge", "public"}]
            if run_id:
                queued = [j for j in queued if j["id"] == run_id]
            if not queued:
                return None
            row = min(queued, key=lambda j: (j["pool"] != "judge", j["created"]))
            con.execute(
                update(jobs)
                .where(jobs.c.id == row["id"])
                .values(status="running", owner=owner, lease_until=time.time() + lease_seconds)
            )
            return dict(row)

    def hook(self, run_id):
        current = None

        def callback(kind, usage):
            nonlocal current
            with self.transaction() as con:
                row = con.execute(select(jobs).where(jobs.c.id == run_id)).mappings().one()
                if kind == "dispatch":
                    self._config(con)
                    if row["status"] != "running":
                        raise Denied("Run is no longer leased")
                    current = str(uuid.uuid4())
                    con.execute(
                        events.insert().values(
                            id=current,
                            run_id=run_id,
                            status="pending",
                            cost=None,
                            data=None,
                            created=time.time(),
                        )
                    )
                    return
                if current is None:
                    raise Denied("Usage has no durable dispatch event")
                cost = nanos(usage.estimated_usd) if usage.estimated_usd is not None else None
                con.execute(
                    update(events)
                    .where(events.c.id == current)
                    .values(status=usage.status, cost=cost, data=usage.model_dump(mode="json"))
                )
                if cost is not None:
                    charged = row["charged"] + cost
                    remaining = row["reserved"] - cost
                    con.execute(
                        update(jobs)
                        .where(jobs.c.id == run_id)
                        .values(charged=charged, reserved=max(0, remaining))
                    )
                    if remaining < 0:
                        con.execute(update(settings).values(enabled=0))
                current = None

        return callback

    def finish(self, run_id, result=None, error=None):
        with self.transaction() as con:
            usage = list(con.execute(select(events).where(events.c.run_id == run_id)).mappings())
            unknown = any(e["cost"] is None for e in usage)
            changes = {
                "status": "failed" if error else "complete",
                "result": result,
                "error": error,
                "lease_until": None,
            }
            if not unknown:
                changes["reserved"] = 0
            con.execute(update(jobs).where(jobs.c.id == run_id).values(**changes))

    def get(self, run_id):
        with self.engine.connect() as con:
            row = con.execute(select(jobs).where(jobs.c.id == run_id)).mappings().first()
            if not row:
                return None
            result = dict(row)
            if result["pool"] in {"public", "judge"} and result["created"] < time.time() - 7 * 86400:
                result["result"] = None
            return result

    def purge_traces(self):
        with self.transaction() as con:
            cutoff = time.time() - 7 * 86400
            con.execute(
                update(jobs)
                .where(jobs.c.created < cutoff, jobs.c.pool.in_(["public", "judge"]))
                .values(result=None)
            )

    def disable(self):
        with self.transaction() as con:
            con.execute(update(settings).values(enabled=0))
