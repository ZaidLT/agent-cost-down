import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from test_ledger import funded

from agent_cost_down.api import create_app
from agent_cost_down.contracts import POLICIES, policy
from agent_cost_down.demo import ScriptedProvider, demonstration, tool
from agent_cost_down.demo import test_catalog as catalog
from agent_cost_down.evaluation.outcomes import evaluate_from_file
from agent_cost_down.protocol import freeze
from agent_cost_down.reporting import build_report


def test_live_api_end_to_end_and_secret_errors(tmp_path, monkeypatch, suite, first):
    monkeypatch.setenv("ACD_LIVE_ENABLED", "true")
    monkeypatch.setenv("ACD_CLIENT_SALT", "local-test-quota-salt")
    monkeypatch.setenv("ACD_JUDGE_CODE", "local-test-judge-secret")
    monkeypatch.setenv("ACD_SUITE", str(suite))
    db = funded("sqlite:///" + str(tmp_path / "hosted.db"))
    models = catalog()
    configs = {pid: policy(models, pid) for pid in POLICIES}
    line = first[1]["lines"][0]

    class HostedTestProvider(ScriptedProvider):
        def __init__(self, hook):
            super().__init__(
                [
                    tool(
                        "submit_draft",
                        {
                            "order_id": line["order_id"],
                            "changes": [{"operation": "replace", "line_id": line["id"], "sku": "BLACK-M"}],
                        },
                    )
                ]
            )
            self.hook = hook

        async def complete(self, model, messages, tools, limits, usage):
            self.hook("dispatch", None)
            result = await super().complete(model, messages, tools, limits, usage)
            self.hook("usage", usage[-1])
            return result

        async def close(self):
            pass

    with TestClient(create_app(db, models, HostedTestProvider, configs)) as client:
        assert client.get("/v1/catalog").json()["available"]
        body = {"task_id": first[0].id, "policy_id": "small_only"}
        response = client.post("/v1/runs", json=body, headers={"Idempotency-Key": "request-123"})
        assert response.status_code == 202
        run_id = response.json()["id"]
        for _ in range(100):
            record = client.get("/v1/runs/" + run_id).json()
            if record["status"] == "complete":
                break
            time.sleep(0.01)
        assert record["status"] == "complete"
        assert record["result"]["outcome"]["success"]
        duplicate = client.post("/v1/runs", json=body, headers={"Idempotency-Key": "request-123"})
        assert duplicate.json()["id"] == run_id
        assert (
            client.post(
                "/v1/runs", json=body, headers={"Idempotency-Key": "request-124", "X-Judge-Code": "wrong"}
            ).status_code
            == 403
        )

        def unavailable(**kwargs):
            raise OperationalError("private connection secret", {}, Exception("secret"))

        monkeypatch.setattr(db, "submit", unavailable)
        response = client.post("/v1/runs", json=body, headers={"Idempotency-Key": "request-125"})
        assert response.status_code == 503
        assert "private connection" not in response.text


@pytest.mark.asyncio
async def test_duplicate_records_and_fixture_relabel_blocked(first, suite):
    record = await demonstration(*first)
    record.outcome = evaluate_from_file(record, suite)
    with pytest.raises(ValueError, match="Duplicate"):
        build_report([record, record], {}, "development", "test_fixture")
    with pytest.raises(ValueError, match="source"):
        build_report([record], {}, "development", "benchmark")


def test_freeze_rejects_scripted_report(suite, tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"source": "test_fixture", "split": "development"}))
    with pytest.raises(ValueError, match="real development"):
        freeze(suite, catalog(), policy(catalog(), "small_only").limits, path, tmp_path / "freeze.json")


def test_hosted_claim_does_not_run_batch_jobs(tmp_path):
    db = funded("sqlite:///" + str(tmp_path / "isolated.db"))
    db.submit(
        task_id="heldout-task",
        policy_id="small_only",
        client="local",
        key="batch",
        pool="evaluation",
        reserve=1,
        payload_hash="hash",
        hosted=False,
    )
    assert db.claim("hosted", hosted=True) is None


def test_context_all_fields_required(first):
    from pydantic import ValidationError

    from agent_cost_down.contracts import FailureContext
    from agent_cost_down.runner import failure

    context = failure("small", "parse_failed", "INVALID_JSON").model_dump()
    for field in context:
        missing = dict(context)
        del missing[field]
        with pytest.raises(ValidationError):
            FailureContext.model_validate_json(json.dumps(missing))
    for field in ["schema_version", "attempt_number"]:
        with pytest.raises(ValidationError):
            FailureContext.model_validate_json(json.dumps({**context, field: True}))
