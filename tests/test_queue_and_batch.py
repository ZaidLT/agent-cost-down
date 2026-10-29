import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_ledger import funded, submit

from agent_cost_down.api import create_app
from agent_cost_down.batch import run_bounded, validate_parallel_pilot
from agent_cost_down.contracts import POLICIES, policy
from agent_cost_down.demo import test_catalog as catalog
from agent_cost_down.ledger import Denied, Ledger, jobs, nanos


def test_queue_dispatch_is_once_and_uncertain_send_cannot_run(tmp_path):
    db = funded("sqlite:///" + str(tmp_path / "queue.db"))
    row = submit(db)
    assert db.begin_dispatch(row["id"])
    assert not db.begin_dispatch(row["id"])
    db.fail_dispatch(row["id"])
    assert db.claim("late-delivery", hosted=True) is None
    assert db.get(row["id"])["reserved"] == 0


def test_failed_ack_does_not_cancel_claimed_run(tmp_path):
    db = funded("sqlite:///" + str(tmp_path / "queue.db"))
    row = submit(db)
    db.begin_dispatch(row["id"])
    assert db.claim("consumer", hosted=True)
    db.fail_dispatch(row["id"])
    assert db.get(row["id"])["status"] == "running"
    assert db.get(row["id"])["reserved"] == nanos(1)
    assert db.claim("duplicate", hosted=True) is None


def test_dispatch_recovery_and_durable_rate_history(tmp_path):
    url = "sqlite:///" + str(tmp_path / "queue.db")
    db = funded(url)
    row = submit(db)
    db.begin_dispatch(row["id"])
    with db.transaction() as con:
        con.execute(update(jobs).values(created=time.time() - 121))
    restarted = Ledger(url)
    restarted.recover_queue()
    assert restarted.get(row["id"])["status"] == "failed"
    assert restarted.get(row["id"])["reserved"] == 0
    assert db.rate_delay(60, 2, 100) == 0
    assert restarted.rate_delay(60, 2, 100) > 0
    with pytest.raises(Denied):
        restarted.rate_delay(101, 2, 100)


def test_queue_api_dispatches_without_local_execution(tmp_path, monkeypatch, suite, first):
    monkeypatch.setenv("ACD_LIVE_ENABLED", "true")
    monkeypatch.setenv("ACD_EXECUTION_MODE", "queue")
    monkeypatch.setenv("ACD_CLIENT_SALT", "test")
    monkeypatch.setenv("ACD_JUDGE_CODE", "test")
    monkeypatch.setenv("ACD_SUITE", str(suite))
    db = funded("sqlite:///" + str(tmp_path / "api.db"))
    models = catalog()
    configs = {pid: policy(models, pid) for pid in POLICIES}
    delivered = []

    async def send(run_id):
        delivered.append(run_id)

    app = create_app(db, models, policies=configs, queue_sender=send)
    with TestClient(app) as client:
        body = {"task_id": first[0].id, "policy_id": "small_only"}
        headers = {"Idempotency-Key": "test-queue-1"}
        first_response = client.post("/v1/runs", json=body, headers=headers)
        assert first_response.status_code == 202
        run_id = first_response.json()["id"]
        assert client.post("/v1/runs", json=body, headers=headers).json()["id"] == run_id
        assert delivered == [run_id]
        assert db.get(run_id)["status"] == "queued"


@pytest.mark.asyncio
async def test_bounded_batch_settles_inflight_and_stops_new_admissions():
    started, settled = [], []

    async def execute(item):
        started.append(item)
        await asyncio.sleep(0 if item == 0 else 0.01)
        if item == 0:
            raise Denied("Budget exhausted")
        settled.append(item)

    with pytest.raises(Denied):
        await run_bounded(range(100), execute, 2)
    assert started == [0, 1]
    assert settled == [1]


def test_parallel_batch_requires_evidence():
    with pytest.raises(ValueError, match="pilot evidence"):
        validate_parallel_pilot(None, catalog(), policy(catalog(), "small_only").limits)


def test_no_expiry_requires_confirmation_and_keeps_judge_allocation(tmp_path):
    from datetime import UTC, datetime

    from pydantic import ValidationError

    from agent_cost_down.ledger import Credits

    evidence = {
        "confirmed_at": datetime.now(UTC).isoformat(),
        "expires_at": None,
        "usable_usd_after_liabilities": 25.0,
        "promotional_only": True,
        "billing_overage_acknowledged": True,
        "evidence_reference": "test-only provider confirmation",
    }
    with pytest.raises(ValidationError, match="no-expiry confirmation"):
        Credits(**evidence)
    credits = Credits(**evidence, no_expiry_confirmed=True)
    db = Ledger("sqlite:///" + str(tmp_path / "nonexpiring.db"))
    db.initialize_schema()
    db.configure(credits)
    assert db.remaining("development") == 2.5
    assert db.remaining("evaluation") == 12.5
    assert db.remaining("judge") == 5.0
    assert db.remaining("public") == 2.5


def test_vercel_uses_integration_branch_url(monkeypatch):
    from agent_cost_down.api import hosted_database_url

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://preview-test")
    monkeypatch.setenv("ACD_DATABASE_URL", "postgresql://production-test")
    assert hosted_database_url() == "postgresql://preview-test"
    monkeypatch.setenv("DATABASE_URL", "postgresql://next-preview-test")
    assert hosted_database_url() == "postgresql://next-preview-test"
    monkeypatch.delenv("VERCEL")
    assert hosted_database_url() == "postgresql://production-test"


def test_branched_preview_cannot_spend_copied_credit(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "preview")
    monkeypatch.setenv("ACD_EXECUTION_MODE", "queue")
    monkeypatch.setenv("ACD_LIVE_ENABLED", "true")
    with pytest.raises(RuntimeError, match="cannot spend"):
        create_app()
