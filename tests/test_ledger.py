import concurrent.futures
import os
from datetime import UTC, datetime, timedelta

import pytest

from agent_cost_down.contracts import Usage
from agent_cost_down.ledger import Credits, Denied, Ledger, metadata, nanos


def funded(url):
    db = Ledger(url)
    db.initialize_schema()
    db.configure(
        Credits(
            confirmed_at=datetime.now(UTC).isoformat(),
            expires_at=(datetime.now(UTC) + timedelta(days=500)).isoformat(),
            usable_usd_after_liabilities=100.0,
            promotional_only=True,
            billing_overage_acknowledged=True,
            topups_disabled=True,
            evidence_reference="test only",
        )
    )
    return db


@pytest.fixture
def db(tmp_path):
    return funded("sqlite:///" + str(tmp_path / "ledger.db"))


def submit(db, key="request-1", client="a", pool="public", reserve=1.0):
    return db.submit(
        task_id="demo",
        policy_id="small_ultra",
        client=client,
        key=key,
        pool=pool,
        reserve=reserve,
        payload_hash="same",
    )


def test_duplicate_idempotency(db):
    one = submit(db)
    assert submit(db)["id"] == one["id"]
    with pytest.raises(Denied):
        db.submit(
            task_id="other",
            policy_id="small_ultra",
            client="a",
            key="request-1",
            pool="public",
            reserve=1,
            payload_hash="different",
        )


def test_public_quota_and_judge_priority(db):
    submit(db)
    submit(db, key="request-2")
    with pytest.raises(Denied, match="quota"):
        submit(db, key="request-3")
    judge = submit(db, key="request-judge", pool="judge")
    assert db.claim("worker")["id"] == judge["id"]
    assert db.claim("other") is None


def test_protected_allocations_and_cap(db):
    submit(db, reserve=10)
    with pytest.raises(Denied, match="allocation"):
        submit(db, key="request-2", client="b", reserve=0.01)
    assert submit(db, key="judge", pool="judge", reserve=20)
    with pytest.raises(Denied, match="allocation"):
        submit(db, key="judge2", pool="judge", reserve=0.01)


def test_concurrent_reservations(db):
    def attempt(i):
        try:
            submit(db, key=str(i), client=str(i), reserve=6)
            return True
        except Denied:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))
    assert sum(results) == 1


def test_ambiguous_charge_retains_reservation(db):
    row = submit(db)
    db.claim("worker")
    hook = db.hook(row["id"])
    hook("dispatch", None)
    hook("usage", Usage(model="x", duration_ms=10.0, status="interrupted"))
    db.finish(row["id"], error="interrupted")
    assert db.get(row["id"])["reserved"] == nanos(1.0)


def test_reconciliation_and_restart(db):
    row = submit(db)
    db.claim("worker")
    hook = db.hook(row["id"])
    hook("dispatch", None)
    hook(
        "usage",
        Usage(
            model="x", input_tokens=10, output_tokens=5, estimated_usd=0.1, duration_ms=10.0, status="success"
        ),
    )
    db.finish(row["id"], {"ok": True})
    assert db.get(row["id"])["reserved"] == 0
    assert db.get(row["id"])["charged"] == nanos(0.1)
    next_run = submit(db, "next", client="b")
    db.claim("worker", lease_seconds=-1)
    assert db.claim("restarted") is None
    assert db.get(next_run["id"])["status"] == "interrupted"
    assert db.get(next_run["id"])["reserved"] == nanos(1)


def test_unconfigured_fails_closed(tmp_path):
    db = Ledger("sqlite:///" + str(tmp_path / "empty.db"))
    db.initialize_schema()
    with pytest.raises(Denied):
        submit(db)


def test_bounded_local_pilot_concurrency(db):
    rows = [
        db.submit(
            task_id="demo",
            policy_id="small_only",
            client="local",
            key=str(i),
            pool="development",
            reserve=1,
            payload_hash=str(i),
            hosted=False,
        )
        for i in range(3)
    ]
    assert db.claim("pilot-1", run_id=rows[0]["id"], max_active=2)
    assert db.claim("pilot-2", run_id=rows[1]["id"], max_active=2)
    assert db.claim("pilot-3", run_id=rows[2]["id"], max_active=2) is None
    with pytest.raises(ValueError):
        db.claim("hosted", hosted=True, max_active=2)


@pytest.mark.skipif(not os.getenv("ACD_TEST_DATABASE_URL"), reason="Requires isolated CI PostgreSQL")
def test_postgres_concurrent_budget_and_duplicates():
    url = os.environ["ACD_TEST_DATABASE_URL"]
    assert "acd_test" in url, "Integration database must explicitly be named acd_test"
    db = Ledger(url)
    metadata.drop_all(db.engine)
    db.engine.dispose()
    db = funded(url)
    test_concurrent_reservations(db)
    assert (
        submit(db, key="duplicate", client="test", pool="judge")["id"]
        == submit(db, key="duplicate", client="test", pool="judge")["id"]
    )
