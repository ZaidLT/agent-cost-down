"""Operational supervisor: forecasts, hard cutoff, and faithful assignment accounting.
Run under caffeinate with the existing ignored environment. Never resets funding.
"""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from agent_cost_down.contracts import POLICIES, Limits, ModelCatalog, digest, policy
from agent_cost_down.ledger import Ledger, jobs
from agent_cost_down.provider import maximum_cost

CUTOFF = datetime.fromisoformat("2026-10-30T08:00:00+03:00")
ROOT = Path(__file__).resolve().parents[1]


def forecast(report, multiplier, available, reservation, *, now=None):
    now = now or datetime.now(UTC)
    if not report['runs'] or any(not r['measurement_complete'] for r in report['runs']):
        raise ValueError('Forecast requires complete measurement evidence')
    usd = multiplier * sum(r['total_estimated_usd'] for r in report['runs'])
    seconds = multiplier * sum(r['duration_ms'] for r in report['runs']) / 1000
    if usd + reservation > available:
        raise ValueError('Forecast and reservation headroom exceed the allocation')
    if now + timedelta(seconds=seconds) > CUTOFF:
        raise ValueError('Forecast exceeds the 08:00 Istanbul cutoff')
    return {'estimated_usd_with_headroom': usd, 'seconds_with_headroom': seconds,
            'reservation_usd': reservation, 'available_usd': available}


def account(batch, db, interrupted=False):
    path = batch / 'assignment.json'
    if not path.exists():
        return
    assignment = json.loads(path.read_text())
    pool = 'evaluation' if assignment['split'] == 'heldout' else 'development'
    rows = []
    for tid, rep, pid in assignment['schedule']:
        result_path = batch / 'runs' / f'{tid}-{rep}-{pid}.json'
        key = digest({'assignment': assignment, 'task': tid, 'repetition': rep, 'policy': pid})
        with db.engine.connect() as con:
            job = con.execute(select(jobs).where(jobs.c.dedupe == f'{pool}:local:{key}')).mappings().first()
        if result_path.exists():
            result = json.loads(result_path.read_text())
            status = 'interrupted' if any(e.get('kind') == 'interrupted' for a in result['attempts'] for e in a['events']) else 'completed'
        elif job and job['status'] != 'queued':
            status = 'interrupted' if interrupted or job['status'] == 'running' else 'failed_without_record'
            if interrupted and job['status'] == 'running':
                db.finish(job['id'], error='Operational cutoff interrupted execution; uncertain charges retained')
        else:
            status = 'not_started'
        rows.append({'task_id': tid, 'repetition': rep, 'policy_id': pid, 'status': status})
    (batch / 'execution-status.json').write_text(json.dumps({'cutoff': CUTOFF.isoformat(),
        'cutoff_reached': interrupted, 'assignments': rows}, indent=2) + '\n')


def run(args, log, batch=None, db=None):
    if datetime.now(UTC) >= CUTOFF:
        raise ValueError('Operational cutoff reached before command')
    command = [str(ROOT / '.venv/bin/acd'), '--suite', 'fixtures-v3', *args]
    process = subprocess.Popen(command, cwd=ROOT, env={**os.environ, 'PYTHONUNBUFFERED': '1'},
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    cutoff = False
    while process.poll() is None:
        left = (CUTOFF - datetime.now(UTC)).total_seconds()
        if left <= 0:
            cutoff = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            break
        time.sleep(min(2, left))
    if batch is not None:
        account(batch, db, cutoff)
    if cutoff or process.returncode:
        raise RuntimeError('Batch stopped at cutoff' if cutoff else f'Command failed with exit {process.returncode}')


def main():
    os.chdir(ROOT)
    if os.getenv('ACD_DATABASE_URL'):
        raise ValueError('Local study must use its existing local ledger')
    db = Ledger('sqlite:///private/operations.db')
    models = ModelCatalog.model_validate_json(Path('private/models.json').read_text())
    maximum = max(maximum_cost(policy(models, p, Limits(deadline_seconds=300))) for p in POLICIES)
    dev = Path('artifacts/development-v4'); held = Path('artifacts/heldout-v4')
    if dev.exists() or held.exists() or Path('artifacts/freeze-v4.json').exists():
        raise ValueError('V4 output already exists; inspect rather than automatically repeat')
    prior = json.loads(Path('artifacts/development-v3-300-report.json').read_text())
    budget = forecast(prior, 1.5, db.remaining('development'), maximum)
    Path('artifacts/v4-development-forecast.json').write_text(json.dumps(budget, indent=2)+'\n')
    with Path('artifacts/v4-study.log').open('x') as log:
        run(['benchmark', '--split', 'development', '--output', str(dev), '--concurrency', '1', '--deadline', '300', '--execute'], log, dev, db)
        run(['report', '--input', str(dev), '--output', 'artifacts/development-v4-report.json'], log)
        run(['benchmark', '--deadline', '300', '--freeze-from', 'artifacts/development-v4-report.json', '--freeze', 'artifacts/freeze-v4.json'], log)
        report = json.loads(Path('artifacts/development-v4-report.json').read_text())
        budget = forecast(report, 4.5, db.remaining('evaluation'), maximum)
        Path('artifacts/v4-heldout-forecast.json').write_text(json.dumps(budget, indent=2)+'\n')
        run(['benchmark', '--split', 'heldout', '--freeze', 'artifacts/freeze-v4.json', '--output', str(held), '--concurrency', '1', '--deadline', '300', '--completion-deadline', CUTOFF.isoformat(), '--execute'], log, held, db)
        run(['report', '--input', str(held), '--output', 'artifacts/heldout-v4-report.json'], log)
    print('V4 study complete. Qualification is recorded in the report; publication remains gated.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - summarize operational failure without replay
        print(f'V4 supervisor stopped: {type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(1) from None
