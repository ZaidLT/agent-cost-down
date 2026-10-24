import ast
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_cost_down.api import create_app
from agent_cost_down.contracts import policy
from agent_cost_down.demo import ScriptedProvider, tool
from agent_cost_down.demo import test_catalog as catalog
from agent_cost_down.evaluation.outcomes import evaluate_from_file
from agent_cost_down.fixtures import generate, load_task
from agent_cost_down.runner import run_policy


def test_generation_deterministic_and_groups_disjoint(suite, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    assert generate(other) == json.loads((suite / "manifest.json").read_text())
    manifest = json.loads((suite / "manifest.json").read_text())
    assert len(manifest["tasks"]) == 40
    dev = {t["template_group"] for t in manifest["tasks"] if t["split"] == "development"}
    held = {t["template_group"] for t in manifest["tasks"] if t["split"] == "heldout"}
    assert not dev & held
    with pytest.raises(ValueError):
        generate(suite)


def test_fixture_hash_tampering(suite):
    task, _ = load_task(suite, "resolution-development-1")
    path = suite / task.snapshot
    path.write_text(path.read_text().replace('"quantity": 2', '"quantity": 99'))
    with pytest.raises(ValueError):
        load_task(suite, task.id)


def test_runtime_has_no_oracle_imports():
    root = Path(__file__).parents[1] / "src/agent_cost_down"
    for name in ["runner.py", "domain.py", "provider.py", "parsing.py"]:
        source = (root / name).read_text()
        assert "private_expected" not in source
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom):
                assert "evaluation" not in (node.module or "")


@pytest.mark.asyncio
async def test_all_generated_oracles_are_consistent(suite):
    manifest = json.loads((suite / "manifest.json").read_text())
    for entry in manifest["tasks"]:
        task, snapshot = load_task(suite, entry["id"])
        oracle = json.loads((suite / "private_expected" / (task.id + ".json")).read_text())
        details = oracle["details"]
        if oracle["resolution"] == "changed":
            field = "sku" if details["operation"] == "replace" else "quantity"
            call = tool(
                "submit_draft",
                {
                    "order_id": details["order_id"],
                    "changes": [
                        {
                            "operation": details["operation"],
                            "line_id": details["line_id"],
                            field: details["value"],
                        }
                    ],
                },
            )
        elif oracle["resolution"] == "answer":
            call = tool("submit_answer", details)
        elif oracle["resolution"] == "clarification":
            call = tool("clarify", {**details, "question": "Please specify the missing information."})
        else:
            index = 1 if task.family == "returns" else 0
            call = tool(
                "refuse",
                {
                    **details,
                    "order_id": snapshot["orders"][index]["id"],
                    "message": "Published rule prevents this.",
                },
            )
        result = await run_policy(
            task, snapshot, policy(catalog(), "small_only"), ScriptedProvider([call]), source="test_fixture"
        )
        assert evaluate_from_file(result, suite).success, task.id


def test_disabled_api_and_request_validation(monkeypatch):
    monkeypatch.setenv("ACD_LIVE_ENABLED", "false")
    with TestClient(create_app()) as client:
        assert client.get("/healthz").json()["live_enabled"] is False
        assert client.get("/v1/catalog").json()["available"] is False
        assert (
            client.post(
                "/v1/runs",
                headers={"Idempotency-Key": "key-12345"},
                json={"task_id": "demo", "policy_id": "small_only", "prompt": "not allowed"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/v1/runs",
                headers={"Idempotency-Key": "key-12345"},
                json={"task_id": "demo", "policy_id": "small_only"},
            ).status_code
            == 503
        )
