import json

import pytest

from agent_cost_down.contracts import policy
from agent_cost_down.demo import ScriptedProvider, tool
from agent_cost_down.demo import test_catalog as catalog
from agent_cost_down.domain import World
from agent_cost_down.evaluation.outcomes import evaluate_from_file
from agent_cost_down.fixtures import load_task
from agent_cost_down.runner import run_policy


@pytest.mark.asyncio
@pytest.mark.parametrize('missing,correct', [(['request'], True), (['request', 'order_id'], True),
                                           (['order_id'], False), (['request', 'quantity'], False)])
async def test_reasonable_clarification_sets(suite, missing, correct):
    task, snapshot = load_task(suite, 'ambiguity-heldout-1')
    record = await run_policy(task, snapshot, policy(catalog(), 'small_only'),
                              ScriptedProvider([tool('clarify', {'missing': missing,
                                                                'question': 'What change and order?'})]),
                              source='test_fixture')
    assert evaluate_from_file(record, suite).success is correct


@pytest.mark.asyncio
async def test_refusal_must_identify_requested_order(suite):
    task, snapshot = load_task(suite, 'ambiguity-heldout-2')
    record = await run_policy(task, snapshot, policy(catalog(), 'small_only'),
                              ScriptedProvider([tool('refuse', {'code': 'out_of_stock',
                                  'order_id': snapshot['orders'][1]['id'], 'message': 'Unavailable'})]),
                              source='test_fixture')
    assert record.verdict == 'ACCEPT'
    assert not evaluate_from_file(record, suite).success


@pytest.mark.parametrize('task_id', [f'analysis-heldout-{i}' for i in range(1, 5)])
def test_analysis_predicates_each_change_the_answer(suite, task_id):
    task, snapshot = load_task(suite, task_id)
    expected = json.loads((suite / 'private_expected' / (task_id + '.json')).read_text())['details']['rows']
    world = World(task, snapshot)
    try:
        base = 'SELECT SUM(l.quantity*p.unit_cents) AS total_cents FROM orders o JOIN lines l ON l.order_id=o.id JOIN products p ON p.sku=l.sku'
        assert world.read_sql(base + " WHERE o.status='open'") != expected
        assert world.read_sql(base + " WHERE o.created_at >= '2026-10-15'") != expected
        assert world.read_sql(base + " WHERE o.status='open' AND o.created_at >= '2026-10-15'") == expected
    finally:
        world.close()


def test_return_window_is_explicit(suite):
    task, _ = load_task(suite, 'returns-heldout-1')
    assert task.rules['return_window_anchor'] == 'order.created_at'
    assert task.rules['return_window_inclusive'] is True


def test_legacy_suite_rejected_before_live_api(monkeypatch, tmp_path):
    from agent_cost_down.api import create_app
    root = tmp_path / 'legacy'
    root.mkdir()
    (root / 'manifest.json').write_text('{"generator_version":"2"}')
    monkeypatch.setenv('ACD_SUITE', str(root))
    monkeypatch.setenv('ACD_LIVE_ENABLED', 'true')
    monkeypatch.setenv('ACD_EXECUTION_MODE', 'local')
    with pytest.raises(ValueError, match='generator version 3'):
        create_app()


@pytest.mark.asyncio
async def test_legacy_suite_rejected_before_cli_reservation(monkeypatch, tmp_path, first):
    from agent_cost_down.cli import execute
    root = tmp_path / 'legacy'
    root.mkdir()
    (root / 'manifest.json').write_text('{"generator_version":"2"}')
    monkeypatch.setenv('ACD_SUITE', str(root))
    monkeypatch.delenv('NEBIUS_API_KEY', raising=False)
    with pytest.raises(ValueError, match='generator version 3'):
        await execute(*first, policy(catalog(), 'small_only'), catalog(), tmp_path / 'run.json',
                      pool='development', key='no-reservation')
