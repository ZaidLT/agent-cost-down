"""Generate a private review packet. This never signs off or changes fixture expectations."""

import html
import json
from pathlib import Path

root = Path("fixtures")
manifest = json.loads((root / "manifest.json").read_text())
parts = [
    '<!doctype html><html lang="en"><meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<title>Agent Cost Down: fixture review</title>',
    '<style>body{max-width:1100px;margin:32px auto;padding:16px;font:16px/1.5 system-ui}',
    'article{border-top:2px solid #ddd;padding:24px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}',
    'summary{cursor:pointer;padding:12px;background:#eee}label{display:block;margin:8px 0}</style>',
    '<h1>Forty-task fixture review</h1>',
    '<p>Private evaluator expectations. Do not bundle this packet into the website or agent tools.</p>',
    '<p>Check the request, authorized customer, rules, original snapshot and expected result for every task.',
    'Inspect positive and negative examples in each family. Record actual reviewer, date, task IDs and',
    'notes in fixtures/review.json only after completing the review. These checkboxes are a reading aid',
    'and do not save or certify review.</p>',
]


def panel(title, data):
    return f"<details><summary>{html.escape(title)}</summary><pre>{html.escape(json.dumps(data, indent=2))}</pre></details>"


for entry in manifest["tasks"]:
    task = json.loads((root / "public" / (entry["id"] + ".json")).read_text())
    snapshot = json.loads((root / task["snapshot"]).read_text())
    expected = json.loads((root / "private_expected" / (entry["id"] + ".json")).read_text())
    parts.extend([
        f'<article><h2>{html.escape(task["id"])}</h2>',
        f'<p>{html.escape(task["request"])}</p>',
        f'<p>Customer: {html.escape(task["customer_id"])}. Date: {html.escape(task["as_of"])}.',
        f' Expected resolution: <strong>{html.escape(expected["resolution"])}</strong>.</p>',
        panel("Public request and business rules", task),
        panel("Before: complete fixture snapshot", snapshot),
        panel("Expected result and independent intent", expected),
        '<label><input type="checkbox"> Request and expected result agree</label>',
        '<label><input type="checkbox"> Scope, rules, stock and unrelated records are correct</label>',
        '<label>Review notes <textarea rows="2" cols="70"></textarea></label></article>',
    ])
parts.append('</html>')
destination = Path("private/fixture-review.html")
destination.parent.mkdir(exist_ok=True)
destination.write_text("\n".join(parts))
print(f"Prepared {len(manifest['tasks'])} tasks for actual human review: {destination}")
