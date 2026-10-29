import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_ledger import submit

from agent_cost_down.ledger import Credits, Denied, Ledger

spec = importlib.util.spec_from_file_location('handoff', Path('scripts/funding_handoff.py'))
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)
IDENTITY = '0123456789abcdef'


def funded(url):
    db = Ledger(url)
    db.initialize_schema()
    db.configure(Credits(confirmed_at=datetime.now(UTC).isoformat(), expires_at=None,
                         no_expiry_confirmed=True, usable_usd_after_liabilities=25.0,
                         promotional_only=True, billing_overage_acknowledged=True,
                         evidence_reference='test only'))
    return db


def test_transfer_is_retired_and_destination_never_refills(tmp_path):
    source = funded('sqlite:///' + str(tmp_path / 'source.db'))
    # Test helper funds $25 in the approved allocation.
    receipt = handoff.prepare(source, IDENTITY)
    assert source.remaining('judge') == source.remaining('public') == 0
    assert handoff.prepare(source, IDENTITY) == receipt
    dest = Ledger('sqlite:///' + str(tmp_path / 'dest.db'))
    dest.initialize_schema()
    assert handoff.receive(dest, receipt, IDENTITY, 'production')
    assert dest.remaining('judge') == 5
    assert dest.remaining('public') == 2.5
    assert dest.remaining('development') == dest.remaining('evaluation') == 0
    submit(dest, pool='judge', reserve=0.5)
    assert not handoff.receive(dest, receipt, IDENTITY, 'production')
    assert dest.remaining('judge') == 4.5
    with pytest.raises(Denied):
        handoff.receive(dest, {**receipt, 'id': 'another'}, IDENTITY, 'production')


@pytest.mark.parametrize('environment,identity', [('preview', IDENTITY), ('production', 'fedcba9876543210')])
def test_wrong_destination_cannot_receive_funds(tmp_path, environment, identity):
    source = funded('sqlite:///' + str(tmp_path / 'source.db'))
    receipt = handoff.prepare(source, IDENTITY)
    dest = Ledger('sqlite:///' + str(tmp_path / 'dest.db'))
    dest.initialize_schema()
    with pytest.raises(Denied):
        handoff.receive(dest, receipt, identity, environment)
    assert not dest.ready()


def test_used_source_pool_cannot_transfer(tmp_path):
    source = funded('sqlite:///' + str(tmp_path / 'source.db'))
    submit(source, pool='public', reserve=0.5)
    with pytest.raises(Denied, match='Reconcile'):
        handoff.prepare(source, IDENTITY)
    assert source.remaining('judge') == 5
    assert source.remaining('public') == 2
