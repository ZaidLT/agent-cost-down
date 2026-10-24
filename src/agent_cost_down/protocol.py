from __future__ import annotations

import json
from pathlib import Path

from .contracts import POLICIES, digest, now, policy


def code_hash():
    root = Path(__file__).parent
    sources = {str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob("*.py"))}
    for name in ("uv.lock", "pyproject.toml"):
        path = root.parents[1] / name
        if path.exists():
            sources[name] = path.read_text()
    return digest(sources)


def freeze(root, catalog, limits, development_report, target):
    manifest = json.loads((root / "manifest.json").read_text())
    report = json.loads(Path(development_report).read_text())
    if report["source"] != "benchmark" or report["split"] != "development":
        raise ValueError("Freeze requires a real development report")
    if report["manifest_hash"] != digest(manifest):
        raise ValueError("Development report uses a different fixture manifest")
    review_path = root / "review.json"
    review = json.loads(review_path.read_text()) if review_path.exists() else {}
    required = {t["id"] for t in manifest["tasks"]}
    if set(review.get("reviewed_task_ids", [])) != required or not review.get("reviewer"):
        raise ValueError("All forty tasks must have a recorded human consistency review")
    configs = {p: policy(catalog, p, limits).model_dump(mode="json") for p in POLICIES}
    expected = {digest(v) for v in configs.values()}
    if any(r["policy_hash"] not in expected for r in report["runs"]):
        raise ValueError("Development settings do not match the proposed freeze")
    if len(report["runs"]) != 100 or any(not r["measurement_complete"] for r in report["runs"]):
        raise ValueError("Forecast requires all 100 development executions with complete cost measurements")
    frozen = {
        "schema_version": 1,
        "created_at": now(),
        "code_hash": code_hash(),
        "manifest_hash": digest(manifest),
        "review_hash": digest(review),
        "catalog": catalog.model_dump(mode="json"),
        "policies": configs,
        "development_report_hash": digest(report),
        "selected": report["recommendation"]["selected"],
        "heldout_repetitions": 3,
        "assigned_per_policy": 60,
        "total_assigned": 300,
        "forecast_usd": 4.5 * sum(r["total_estimated_usd"] for r in report["runs"]),
        "forecast_seconds": 4.5 * sum(r["duration_ms"] for r in report["runs"]) / 1000,
    }
    path = Path(target)
    if path.exists():
        raise ValueError("Freeze file already exists")
    path.write_text(json.dumps(frozen, indent=2) + "\n")
    return frozen


def verify_freeze(root, frozen):
    manifest = json.loads((root / "manifest.json").read_text())
    if frozen["code_hash"] != code_hash() or frozen["manifest_hash"] != digest(manifest):
        raise ValueError("Code or fixtures changed after freeze. Create a new protocol version.")
    if frozen["review_hash"] != digest(json.loads((root / "review.json").read_text())):
        raise ValueError("Fixture review changed")
    return manifest
