import copy

import pytest

from agent_cost_down.contracts import digest, policy
from agent_cost_down.demo import ScriptedProvider, tool
from agent_cost_down.demo import test_catalog as catalog
from agent_cost_down.domain import Draft, ToolFailure, World, validated_pointer
from agent_cost_down.runner import run_policy


@pytest.mark.parametrize('operation', ['replace', 'quantity', 'return'])
def test_redundant_field_and_conflict(first, operation):
    task, state = first
    state = copy.deepcopy(state)
    order = next(o for o in state['orders'] if o['customer_id'] == task.customer_id)
    line = next(l for l in state['lines'] if l['order_id'] == order['id'])
    if operation == 'return':
        order['status'] = 'delivered'
        task = task.model_copy(update={'snapshot_hash': digest(state)})
    change = {'operation': operation, 'line_id': line['id'], 'sku': line['sku'], 'quantity': line['quantity']}
    world = World(task, state)
    try:
        verdict, _, _ = world.finish('submit_draft', Draft(order_id=order['id'], changes=[change]))
        assert verdict == 'ACCEPT'
    finally:
        world.close()
    bad_field = 'quantity' if operation == 'replace' else 'sku'
    change[bad_field] = line['quantity'] + 1 if bad_field == 'quantity' else 'DIFFERENT'
    world = World(task, state)
    try:
        with pytest.raises(ToolFailure) as exc:
            world.finish('submit_draft', Draft(order_id=order['id'], changes=[change]))
        assert exc.value.code == ('CONFLICTING_QUANTITY' if bad_field == 'quantity' else 'CONFLICTING_SKU')
        assert validated_pointer('submit_draft', exc.value.field, {'changes': [change]}, world.types())
        assert world.state() == state
    finally:
        world.close()


@pytest.mark.asyncio
async def test_missing_tool_distinct_from_bad_json(first):
    class MissingTool(ScriptedProvider):
        async def complete(self, *args):
            return {'content': 'No action', 'tool_calls': []}
    missing = await run_policy(*first, policy(catalog(), 'small_only'), MissingTool([]))
    malformed = await run_policy(*first, policy(catalog(), 'small_only'), ScriptedProvider([tool('submit_draft', {}, raw='{')]))
    assert missing.attempts[0].failure_context.observations[0].code == 'NO_TOOL_CALL'
    assert malformed.attempts[0].failure_context.observations[0].code == 'INVALID_JSON'
    assert missing.attempts[0].failure_context.schema_version == 2


@pytest.mark.asyncio
async def test_old_policy_readable_but_cannot_execute(first):
    config = policy(catalog(), 'small_only').model_copy(update={'validator_version': '1'})
    with pytest.raises(ValueError, match='validator version 2'):
        await run_policy(*first, config, ScriptedProvider([]))


@pytest.mark.asyncio
async def test_specific_feedback_preserves_original_snapshot(first):
    task, state = first
    order = next(o for o in state['orders'] if o['customer_id'] == task.customer_id)
    line = next(l for l in state['lines'] if l['order_id'] == order['id'])
    bad = {'order_id': order['id'], 'changes': [{'operation': 'replace', 'line_id': line['id'], 'sku': line['sku'], 'quantity': line['quantity'] + 1}]}
    good = copy.deepcopy(bad)
    good['changes'][0]['quantity'] = line['quantity']
    provider = ScriptedProvider([tool('submit_draft', bad), tool('submit_draft', good)])
    run = await run_policy(task, state, policy(catalog(), 'small_retry'), provider)
    obs = run.attempts[0].failure_context.observations[0]
    assert obs.code == 'CONFLICTING_QUANTITY'
    assert obs.field == '/changes/0/quantity'
    assert run.verdict == 'ACCEPT'
    assert run.after == state


@pytest.mark.asyncio
async def test_report_rejects_mixed_versions_and_configs(first, suite):
    from agent_cost_down.demo import demonstration
    from agent_cost_down.evaluation.outcomes import evaluate_from_file
    from agent_cost_down.reporting import build_report
    run = await demonstration(*first)
    run.outcome = evaluate_from_file(run, suite)
    other = run.model_copy(deep=True)
    other.repetition = 1
    other.policy.validator_version = '1'
    other.policy_hash = digest(other.policy)
    with pytest.raises(ValueError, match='Mixed'):
        build_report([run, other], {}, 'development', 'test_fixture')
    with pytest.raises(ValueError, match='assigned hash'):
        build_report([run], {}, 'development', 'test_fixture', provenance={'configs': {run.policy.id: 'wrong'}})


def test_supervisor_forecast_limits():
    import importlib.util
    from datetime import UTC, datetime
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('v4_supervisor', Path('scripts/run_v4_study.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = {'runs': [{'measurement_complete': True, 'total_estimated_usd': 1, 'duration_ms': 1000}]}
    now = datetime(2026, 10, 30, 0, 0, tzinfo=UTC)
    assert module.forecast(report, 1.5, 3, 1.5, now=now)['estimated_usd_with_headroom'] == 1.5
    with pytest.raises(ValueError, match='allocation'):
        module.forecast(report, 1.5, 2.99, 1.5, now=now)
    with pytest.raises(ValueError, match='cutoff'):
        module.forecast(report, 1.5, 3, 1.5, now=module.CUTOFF)
