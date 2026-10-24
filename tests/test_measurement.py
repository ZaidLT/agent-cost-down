import json

import httpx
import pytest

from agent_cost_down.contracts import Limits, ModelSpec, policy
from agent_cost_down.demo import demonstration
from agent_cost_down.demo import test_catalog as catalog
from agent_cost_down.evaluation.outcomes import evaluate_from_file
from agent_cost_down.privacy import public_export, scrub
from agent_cost_down.provider import ProviderFailure, TokenFactory, maximum_cost
from agent_cost_down.reporting import build_report


@pytest.mark.asyncio
async def test_usage_and_no_hidden_retries():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "usage": {"prompt_tokens": 1000, "completion_tokens": 100},
                "choices": [{"message": {"tool_calls": []}}],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://example.test/v1/")
    p = TokenFactory(60, 1000000, client)
    usage = []
    model = ModelSpec(id="test", input_usd_per_million=1.0, output_usd_per_million=2.0)
    await p.complete(model, [], [], Limits(), usage)
    assert len(requests) == 1 and len(usage) == 1
    assert usage[0].estimated_usd == pytest.approx(0.0012)
    assert json.loads(requests[0].content)["max_tokens"] == 4096
    await p.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"error": "secret raw error"}),
        httpx.Response(200, json={"choices": [{"message": {}}]}),
    ],
)
async def test_error_or_missing_usage_never_free(response):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: response), base_url="https://example.test/v1/"
    )
    p = TokenFactory(60, 1000000, client)
    usage = []
    try:
        await p.complete(catalog().models["small"], [], [], Limits(), usage)
    except ProviderFailure as exc:
        assert "secret raw error" not in str(exc)
    assert len(usage) == 1
    assert usage[0].estimated_usd is None
    await p.close()


@pytest.mark.asyncio
async def test_ambiguous_request_not_retried():
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        raise httpx.ReadTimeout("private error")

    p = TokenFactory(
        60,
        1000000,
        httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://example.test/v1/"),
    )
    usage = []
    with pytest.raises(ProviderFailure):
        await p.complete(catalog().models["small"], [], [], Limits(), usage)
    assert count == 1 and usage[0].estimated_usd is None
    await p.close()


def test_secret_publication_gate(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "actual-secret-123456789")
    value = {"trace": "actual-secret-123456789", "key": "ACD_SECRET_CANARY_ABC"}
    with pytest.raises(ValueError):
        public_export(value)
    assert "actual-secret" not in json.dumps(scrub(value))
    with pytest.raises(ValueError):
        public_export({"authorization": "anything"})


@pytest.mark.asyncio
async def test_report_denominator_cost_and_no_claim_on_fixture(first, suite):
    run = await demonstration(*first)
    run.outcome = evaluate_from_file(run, suite)
    report = build_report(
        [run], {}, "heldout", "test_fixture", selected="small_ultra", assigned_per_policy=60
    )
    p = next(p for p in report.policies if p["id"] == "small_ultra")
    assert p["successes"] == 1 and p["assigned"] == 60
    assert p["total_estimated_usd"] is None
    assert p["incomplete_measurements"] == 59
    assert not p["qualifies"]
    assert report.recommendation["status"] == "test_fixture"


def test_conservative_reservation():
    config = policy(catalog(), "small_ultra")
    config.models[0].input_usd_per_million = 1
    config.models[1].output_usd_per_million = 10
    assert maximum_cost(config) > 0
