"""Validate and copy a genuine versioned report into the static explorer."""

import argparse
import json
from pathlib import Path

from agent_cost_down.contracts import BenchmarkReport, canonical
from agent_cost_down.privacy import public_export
from agent_cost_down.reporting import build_report

parser = argparse.ArgumentParser()
parser.add_argument("report")
parser.add_argument("--destination", default="frontend/public/reports")
args = parser.parse_args()
report = BenchmarkReport.model_validate_json(Path(args.report).read_text())
if report.source != "benchmark":
    raise SystemExit("Only a genuine benchmark may replace the active model report")
if report.split != "heldout":
    raise SystemExit("The submitted comparison requires the held-out report")
# Recompute every policy metric from raw runs and the original assigned denominator.
assignment = report.provenance
rebuilt = build_report(
    report.runs,
    {},
    report.split,
    report.source,
    selected=report.recommendation["selected"],
    assigned_per_policy=len(assignment["schedule"]) // 5,
    provenance=assignment,
)
if len(report.runs) != 300 or len(assignment["schedule"]) != 300:
    raise SystemExit("Only the complete 300-assignment report can replace the primary report")
# Legacy reports retain their original fields; verify every originally displayed metric.
reproduced = [{k: new[k] for k in old} for old, new in zip(report.policies, rebuilt.policies, strict=True)]
if (
    canonical(reproduced) != canonical(report.policies)
    or rebuilt.recommendation != report.recommendation
):
    raise SystemExit("Report aggregate or recommendation differs from raw evidence")
destination = Path(args.destination)
destination.mkdir(parents=True, exist_ok=True)
target = destination / (report.id + ".json")
payload = canonical(public_export(report.model_dump(mode="json"))) + "\n"
if target.exists() and target.read_text() != payload:
    raise SystemExit("A published report is immutable")
target.write_text(payload)
index_path = destination / "index.json"
index = json.loads(index_path.read_text()) if index_path.exists() else {}
archives = [x for x in index.get("reports", []) if x["file"] != target.name]
archives.append({"file": target.name, "label": "v4 controlled rerun" if report.provenance.get("reused_suite") else "v3 original study"})
index_path.write_text(json.dumps({"active": target.name, "status": report.recommendation["status"], "reports": archives}) + "\n")
policies = {r.policy.id: r.policy.model_dump(mode="json") for r in report.runs}
(destination / (report.id + "-policies.json")).write_text(json.dumps(policies, indent=2) + "\n")
print("Published validated artifacts; qualification remains " + report.recommendation["status"])
