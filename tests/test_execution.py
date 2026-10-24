import json

import pytest
from pydantic import ValidationError

from agent_cost_down.contracts import FailureContext, digest, policy
from agent_cost_down.demo import ScriptedProvider, demonstration, tool
from agent_cost_down.demo import test_catalog as catalog
from agent_cost_down.domain import Draft, ToolFailure, World, validated_pointer
from agent_cost_down.evaluation.outcomes import evaluate_from_file
from agent_cost_down.fixtures import load_task
from agent_cost_down.parsing import ParseFailure, parse_arguments
from agent_cost_down.runner import failure, run_policy


@pytest.mark.parametrize(
    "raw",
    [
        '{"a":',
        '{"a":1} {"b":2}',
        "[]",
        '{"a":1,"a":2}',
        '{"a":NaN}',
        chr(96) * 3 + "json\n{}\n" + chr(96) * 3 + "prose",
    ],
)
def test_rejects_malformed_arguments(raw):
    with pytest.raises(ParseFailure):
        parse_arguments(raw)


def test_normalization_preserves_string_whitespace():
    raw = (
        "\ufeff "
        + chr(96) * 3
        + 'json\n{"nested":{"quote":"a \\"b\\"  ","spaces":"  keep\\n "}}\n'
        + chr(96) * 3
        + " "
    )
    value, normalized = parse_arguments(raw)
    assert normalized
    assert value["nested"]["spaces"] == "  keep\n "
    assert value["nested"]["quote"] == 'a "b"  '


def test_wrong_types_and_unknown_fields():
    with pytest.raises(ValidationError):
        Draft.model_validate(
            {"order_id": "a", "changes": [{"operation": "quantity", "line_id": "b", "quantity": "2"}]}
        )
    with pytest.raises(ValidationError):
        Draft.model_validate(
            {
                "order_id": "a",
                "changes": [{"operation": "quantity", "line_id": "b", "quantity": 2}],
                "oracle": 1,
            }
        )


def test_failure_context_contract_and_paths(first):
    task, snapshot = first
    world = World(task, snapshot)
    args = {"changes": [{"quantity": "2"}]}
    assert validated_pointer("submit_draft", "/changes/0/quantity", args, world.types())
    assert not validated_pointer("submit_draft", "/changes/2/quantity", args, world.types())
    assert not validated_pointer("submit_draft", "/expected_answer", args, world.types())
    assert not validated_pointer("unknown", None, args, world.types())
    context = failure("model", "parse_failed", "INVALID_JSON")
    with pytest.raises(ValidationError):
        FailureContext.model_validate_json(json.dumps({**context.model_dump(), "hidden_answer": "x"}))
    with pytest.raises(ValidationError):
        FailureContext.model_validate_json(json.dumps({**context.model_dump(), "source_model": "a" * 3000}))
    world.close()


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM orders",
        "UPDATE stock SET available=999",
        "ATTACH DATABASE '/tmp/x' AS x",
        "PRAGMA table_info(orders)",
        "SELECT load_extension('x')",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM orders; DELETE FROM lines",
        "WITH RECURSIVE t(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM t) SELECT sum(x) FROM t",
    ],
)
def test_sql_denies_unsafe_or_unbounded_queries(first, query):
    world = World(*first)
    before = world.state()
    with pytest.raises(ToolFailure):
        world.read_sql(query)
    assert world.state() == before
    world.close()


def test_sql_and_get_order_scope(first):
    task, snapshot = first
    world = World(task, snapshot)
    assert all(r["customer_id"] == task.customer_id for r in world.read_sql("SELECT * FROM orders"))
    foreign = next(o for o in snapshot["orders"] if o["customer_id"] != task.customer_id)
    with pytest.raises(ToolFailure):
        world.order(foreign["id"])
    assert not world.read_sql("SELECT * FROM lines WHERE order_id='" + foreign["id"] + "'")
    world.close()


def test_atomic_rollback_and_unrelated_rows(first):
    task, snapshot = first
    world = World(task, snapshot)
    own = snapshot["orders"][0]["id"]
    lines = [l for l in snapshot["lines"] if l["order_id"] == own]
    draft = Draft(
        order_id=own,
        changes=[
            {"operation": "quantity", "line_id": lines[0]["id"], "quantity": 3},
            {"operation": "replace", "line_id": lines[1]["id"], "sku": "NONEXISTENT"},
        ],
    )
    before = world.state()
    with pytest.raises(ToolFailure):
        world.finish("submit_draft", draft)
    assert world.state() == before
    world.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pid,attempts",
    [("small_only", 1), ("super_only", 1), ("ultra_only", 1), ("small_retry", 2), ("small_ultra", 2)],
)
async def test_policies_and_independent_result(first, suite, pid, attempts):
    record = await demonstration(*first, pid)
    assert len(record.attempts) == attempts
    assert record.verdict == "ACCEPT"
    assert evaluate_from_file(record, suite).success
    assert record.source == "test_fixture"


@pytest.mark.asyncio
async def test_wrong_but_valid_action_passes_runtime_and_fails_oracle(first, suite):
    task, snapshot = first
    line = snapshot["lines"][0]
    provider = ScriptedProvider(
        [
            tool(
                "submit_draft",
                {
                    "order_id": line["order_id"],
                    "changes": [{"operation": "quantity", "line_id": line["id"], "quantity": 4}],
                },
            )
        ]
    )
    record = await run_policy(
        task, snapshot, policy(catalog(), "small_ultra"), provider, source="test_fixture"
    )
    assert record.verdict == "ACCEPT"
    assert len(record.attempts) == 1
    assert not evaluate_from_file(record, suite).success


@pytest.mark.asyncio
async def test_clean_restart_equivalent_context(first):
    task, snapshot = first
    line = snapshot["lines"][0]
    rejected = tool(
        "submit_draft",
        {
            "order_id": line["order_id"],
            "changes": [{"operation": "quantity", "line_id": line["id"], "quantity": 100}],
        },
    )
    accepted = tool(
        "submit_draft",
        {
            "order_id": line["order_id"],
            "changes": [{"operation": "replace", "line_id": line["id"], "sku": "BLACK-M"}],
        },
    )
    contexts = []
    for pid in ["small_retry", "small_ultra"]:
        p = ScriptedProvider([rejected, accepted])
        record = await run_policy(task, snapshot, policy(catalog(), pid), p, source="test_fixture")
        assert record.attempts[0].state_hash == digest(snapshot)
        assert len(record.attempts) == 2
        contexts.append(json.loads(p.seen[1]["messages"][1]["content"])["previous_failure"])
    assert contexts[0] == contexts[1]
    assert "expected_state" not in json.dumps(contexts)


@pytest.mark.asyncio
async def test_exhaustion(first):
    p = ScriptedProvider([tool("unknown", {}), tool("unknown", {})])
    record = await run_policy(*first, policy(catalog(), "small_ultra"), p, source="test_fixture")
    assert record.verdict == "UNRESOLVED"
    assert record.before == record.after
    assert all(a.failure_context.observations[0].tool is None for a in record.attempts)


@pytest.mark.asyncio
async def test_multiple_terminal_calls_never_commit(first):
    p = ScriptedProvider([{"tool_calls": [tool("submit_answer", {"rows": []})["tool_calls"][0]] * 2}])
    record = await run_policy(*first, policy(catalog(), "small_only"), p, source="test_fixture")
    assert record.verdict == "UNRESOLVED"
    assert record.before == record.after


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "task_id",
    ["ambiguity-development-1", "ambiguity-development-2", "returns-development-2", "analysis-development-1"],
)
async def test_nonmutating_resolutions(suite, task_id):
    task, snapshot = load_task(suite, task_id)
    oracle = json.loads((suite / "private_expected" / (task_id + ".json")).read_text())
    if oracle["resolution"] == "clarification":
        reply = tool("clarify", {"missing": oracle["details"]["missing"], "question": "What quantity?"})
    elif oracle["resolution"] == "refused":
        order = snapshot["orders"][1 if task.family == "returns" else 0]
        reply = tool(
            "refuse",
            {
                "code": oracle["details"]["code"],
                "order_id": order["id"],
                "message": "Published rule prevents this.",
            },
        )
    else:
        reply = tool("submit_answer", oracle["details"])
    record = await run_policy(
        task, snapshot, policy(catalog(), "small_ultra"), ScriptedProvider([reply]), source="test_fixture"
    )
    assert evaluate_from_file(record, suite).success
    assert record.before == record.after
    assert len(record.attempts) == 1


@pytest.mark.asyncio
async def test_evaluator_rejects_receipt_state_and_foreign_mutation(first, suite):
    record = await demonstration(*first)
    altered = record.model_copy(deep=True)
    altered.attempts[-1].result["order_id"] = "wrong"
    assert not evaluate_from_file(altered, suite).success
    altered = record.model_copy(deep=True)
    altered.after["lines"][-1]["quantity"] += 1
    outcome = evaluate_from_file(altered, suite)
    assert not outcome.success
    assert outcome.critical_error
    altered = record.model_copy(deep=True)
    altered.after["lines"][0]["sku"] = "BLACK-L"
    assert not evaluate_from_file(altered, suite).success


@pytest.mark.asyncio
async def test_second_inventory_adapter(first):
    task, snapshot = first
    task = task.model_copy(
        update={"adapter": "inventory", "id": "inventory-1", "request": "Reserve two mugs."}
    )
    provider = ScriptedProvider([tool("reserve_inventory", {"sku": "MUG", "quantity": 2})])
    record = await run_policy(
        task, snapshot, policy(catalog(), "small_only", adapter="inventory"), provider, source="test_fixture"
    )
    assert record.resolution == "reserved"
    assert (
        next(x for x in record.after["stock"] if x["sku"] == "MUG")["available"]
        == next(x for x in snapshot["stock"] if x["sku"] == "MUG")["available"] - 2
    )
    assert record.after["orders"] == snapshot["orders"]
