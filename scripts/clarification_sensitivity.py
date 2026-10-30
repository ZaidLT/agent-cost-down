"""Post-hoc presentation analysis only. Never changes scores, fixtures or model calls."""
import hashlib
import json
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parent.parent
reports = {}
for version in (3, 4):
    path = root / f'evidence/v{version}/heldout-report.json'
    raw = path.read_bytes()
    reports[version] = (json.loads(raw), hashlib.sha256(raw).hexdigest())
replay = json.loads((root / 'frontend/src/data/v3-replay.json').read_text())['reports']


def cause(report, run):
    if run['outcome']['success']:
        return None
    if run['verdict'] == 'CLARIFY' and not run['outcome']['checks']['response']:
        fields = (run['attempts'][-1]['result'] or {}).get('missing')
        if run['task']['request'] == 'Please update my order.' and isinstance(fields, list):
            return 'clarification_extra_fields' if 'request' in fields else 'clarification_missing_request'
        return 'clarification'
    if run['verdict'] == 'ACCEPT':
        return 'incorrect'
    if run['verdict'] in ('INTERRUPTED', 'DEADLINE'):
        return 'deadline'
    a = run['attempts'][-1]
    context = a.get('failure_context') or {}
    codes = [e.get('code', '') for e in a['events']] + [o['code'] for o in context.get('observations', [])]
    reason = context.get('reason', '')
    if 'NO_TOOL_CALL' in codes:
        return 'missing'
    if run['id'] + ':' + str(len(run['attempts']) - 1) in replay.get(report['id'], {}).get('attempts', []):
        return 'contract'
    if any(any(word in c for word in ('DEADLINE', 'TIMEOUT', 'INTERRUPT')) for c in codes) or any(word in reason for word in ('deadline', 'interrupted')):
        return 'deadline'
    if any(e['kind'] == 'provider_failure' for e in a['events']) or 'provider' in reason:
        return 'provider'
    if reason == 'tool_schema_failed' or any('SCHEMA' in c or 'INVALID_ARGUMENT_TYPE' in c for c in codes):
        return 'schema'
    if 'INVALID_JSON' in codes or reason == 'parse_failed':
        return 'json'
    if reason == 'runtime_validation_failed' or 'BUSINESS_RULE_VIOLATION' in codes:
        return 'runtime'
    return 'unclassified'


comparison = {'source': 'post_hoc_diagnostic_summary', 'model_calls': 0, 'reports': {}}
for version, (report, sha) in reports.items():
    groups = {}
    for run in report['runs']:
        category = cause(report, run)
        if category:
            groups.setdefault(category, []).append(run['id'])
    comparison['reports'][report['id']] = {
        'version': f'v{version}', 'file': report['id'] + '.json', 'sha256': sha,
        'total_final_failures': sum(map(len, groups.values())), 'categories': groups,
    }

report, sha = reports[4]
analysis = {
    'source': 'post_hoc_sensitivity_analysis', 'model_calls': 0, 'report_id': report['id'],
    'report_sha256': sha, 'frozen_scores_unchanged': True,
    'rule': 'For Please update my order. clarifications only, accept any structured missing-field set containing request, provided every other frozen outcome check passes.',
    'limitations': 'This is an alternative scoring rule inspected after results, not new inference, human semantic grading, a replacement recommendation, or independent validation. Free-text questions are not rescored.',
    'policies': {}, 'clarification_failures': [],
}
for policy in report['policies']:
    policy_runs = [r for r in report['runs'] if r['policy']['id'] == policy['id']]
    additions = []
    for run in policy_runs:
        if run['verdict'] != 'CLARIFY' or run['outcome']['success'] or run['outcome']['checks']['response']:
            continue
        result = run['attempts'][-1]['result'] or {}
        fields = result.get('missing', [])
        broader_pass = (
            run['task']['request'] == 'Please update my order.' and 'request' in fields
            and all(v for k, v in run['outcome']['checks'].items() if k != 'response')
            and not run['outcome']['critical_error']
        )
        analysis['clarification_failures'].append({
            'run_id': run['id'], 'task_id': run['task']['id'], 'policy_id': policy['id'],
            'missing': fields, 'question': result.get('question'), 'broader_rule_pass': broader_pass,
        })
        if broader_pass:
            additions.append(run['id'])
    analysis['policies'][policy['id']] = {
        'assigned': policy['assigned'], 'frozen_successes': policy['successes'],
        'broader_successes': policy['successes'] + len(additions), 'changed_run_ids': additions,
    }
assert len(analysis['clarification_failures']) == 16
assert {k: v['broader_successes'] for k, v in analysis['policies'].items()} == {
    'small_only': 53, 'super_only': 52, 'ultra_only': 60, 'small_retry': 55, 'small_ultra': 57,
}
assert comparison['reports'][report['id']]['total_final_failures'] == 27
for name, value in [('clarification-sensitivity', analysis), ('diagnosis-comparison', comparison)]:
    target = root / f'frontend/src/data/{name}.json'
    target.write_text(json.dumps(value, indent=2) + '\n')
print(json.dumps({'frozen_scores_unchanged': True, 'broader_successes': {k: v['broader_successes'] for k, v in analysis['policies'].items()}, 'clarification_categories': dict(Counter(cause(report, r) for r in report['runs'] if r['verdict'] == 'CLARIFY' and not r['outcome']['success']))}, indent=2))
