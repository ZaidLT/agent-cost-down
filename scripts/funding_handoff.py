"""Explicit, idempotent transfer of unused demo allocations. Never invokes inference."""

import argparse
import json
import re
import uuid
from pathlib import Path

from sqlalchemy import JSON, Column, MetaData, String, Table, insert, select, update

from agent_cost_down.contracts import digest, now
from agent_cost_down.ledger import Denied, Ledger, jobs, settings

metadata = MetaData()
transfers = Table('funding_transfers', metadata, Column('id', String, primary_key=True),
                  Column('destination', String, nullable=False), Column('receipt', JSON, nullable=False))
POOLS = ('judge', 'public')


def prepare(db, destination):
    if not re.fullmatch(r'[0-9a-f]{16}', destination):
        raise ValueError('Use the verified production database fingerprint')
    metadata.create_all(db.engine)
    with db.transaction() as con:
        prior = con.execute(select(transfers)).mappings().first()
        if prior:
            if prior['destination'] != destination:
                raise Denied('Funding already assigned to another destination')
            return prior['receipt']
        config = db._config(con)
        if con.execute(select(jobs.c.id).where(jobs.c.pool.in_(POOLS))).first():
            raise Denied('Reconcile existing demo jobs before transferring allocations')
        amounts = {pool: config['allocations'].get(pool, 0) for pool in POOLS}
        if amounts != {'judge': 5_000_000_000, 'public': 2_500_000_000}:
            raise Denied('Transfer requires the approved unused $5/$2.50 allocations')
        receipt = {'id': str(uuid.uuid4()), 'created_at': now(), 'destination': destination,
                   'allocations_nanos': amounts, 'expires': config['expires'],
                   'source_allocations_retired': True}
        remaining = {**config['allocations'], **{pool: 0 for pool in POOLS}}
        con.execute(update(settings).where(settings.c.id == 1).values(allocations=remaining))
        con.execute(insert(transfers).values(id=receipt['id'], destination=destination, receipt=receipt))
        return receipt


def receive(db, receipt, identity, environment):
    if environment != 'production' or receipt.get('destination') != identity:
        raise Denied('Funding may only reach the named production database')
    amounts = receipt.get('allocations_nanos')
    if receipt.get('source_allocations_retired') is not True or amounts != {
        'judge': 5_000_000_000, 'public': 2_500_000_000
    }:
        raise Denied('Invalid transfer receipt')
    metadata.create_all(db.engine)
    with db.transaction() as con:
        prior = con.execute(select(transfers).where(transfers.c.id == receipt['id'])).mappings().first()
        if prior:
            if digest(prior['receipt']) != digest(receipt):
                raise Denied('Transfer receipt changed')
            return False
        if con.execute(select(settings)).first() or con.execute(select(transfers)).first():
            raise Denied('Destination already funded; never reset its accounting')
        con.execute(insert(settings).values(id=1, allocations={**amounts, 'development': 0, 'evaluation': 0},
                                            expires=receipt['expires'], enabled=1))
        con.execute(insert(transfers).values(id=receipt['id'], destination=identity, receipt=receipt))
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='sqlite:///private/operations.db')
    parser.add_argument('--destination-fingerprint', required=True)
    parser.add_argument('--receipt', default='private/hosted-funding-receipt.json')
    args = parser.parse_args()
    db = Ledger(args.source)
    receipt = prepare(db, args.destination_fingerprint)
    path = Path(args.receipt)
    if path.exists() and json.loads(path.read_text()) != receipt:
        raise SystemExit('Existing receipt differs; source retirement remains recorded in the database')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    path.chmod(0o600)
    print('Demo allocations retired locally; private receipt saved. No hosted funding or inference started.')
