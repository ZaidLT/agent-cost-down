from __future__ import annotations

import math
import statistics
from pathlib import Path

from .contracts import BenchmarkReport, RunRecord, digest, now
from .privacy import public_export


def percentile(values, fraction):
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def summarize(runs, assigned):
    success = sum(bool(r.outcome and r.outcome.success) for r in runs)
    accepted = [r for r in runs if r.verdict == "ACCEPT"]
    wrong = [r.id for r in accepted if r.outcome and not r.outcome.success]
    wrong_mutations = [
        r.id
        for r in accepted
        if r.resolution in {"changed", "reserved"} and r.outcome and not r.outcome.success
    ]
    complete = len(runs) == assigned and all(r.measurement_complete for r in runs)
    cost = sum(r.total_estimated_usd or 0 for r in runs) if complete else None
    attempts = [a for r in runs for a in r.attempts]
    parsed = sum(a.parsed_calls for a in attempts)
    return {
        "assigned": assigned,
        "completed": len(runs),
        "successes": success,
        "success_rate": success / assigned if assigned else 0,
        "incorrect_accepted": wrong,
        "incorrect_accepted_mutations": wrong_mutations,
        "incorrect_accepted_rate": len(wrong) / len(accepted) if accepted else 0,
        "incorrect_accepted_all_rate": len(wrong) / assigned if assigned else 0,
        "critical_errors": sum(
            bool(r.outcome and r.outcome.critical_error and r.verdict == "ACCEPT") for r in runs
        ),
        "total_estimated_usd": cost,
        "cost_per_success": cost / success if cost is not None and success else None,
        "median_ms": statistics.median([r.duration_ms for r in runs]) if runs else None,
        "p95_ms": percentile([r.duration_ms for r in runs], 0.95),
        "escalation_rate": sum(len(r.attempts) == 2 for r in runs) / assigned if assigned else 0,
        "rejection_rate": sum(a.verdict == "RETRY" for a in attempts) / len(attempts) if attempts else 0,
        "normalization_rate": sum(a.normalized_calls for a in attempts) / parsed if parsed else 0,
        "incomplete_measurements": assigned - sum(r.measurement_complete for r in runs),
        "escalated_runs": sum(len(r.attempts) == 2 for r in runs),
        "recovered_runs": sum(len(r.attempts) == 2 and bool(r.outcome and r.outcome.success) for r in runs),
        "clarification_failures": sum(r.verdict == "CLARIFY" and bool(r.outcome and not r.outcome.success) for r in runs),
        "provider_failures": sum(any(e.get("kind") == "provider_failure" for a in r.attempts for e in a.events) for r in runs),
        "deadline_interruptions": sum(any(e.get("kind") == "interrupted" for a in r.attempts for e in a.events) for r in runs),
    }


def build_report(runs, manifest, split, source, *, selected=None, assigned_per_policy=None, provenance=None):
    from .contracts import POLICIES

    keys = [(r.task.id, r.repetition, r.policy.id) for r in runs]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate assigned executions in report")
    if any(
        r.source != source or r.task_hash != digest(r.task) or r.policy_hash != digest(r.policy) for r in runs
    ):
        raise ValueError("Report source or run provenance mismatch")
    if source == "benchmark" and any(r.outcome is None for r in runs):
        raise ValueError("Completed benchmark records require independent outcomes")
    if provenance and "schedule" in provenance:
        schedule = {tuple(k) for k in provenance["schedule"]}
        if not set(keys) <= schedule:
            raise ValueError("Report includes an execution outside the assigned schedule")

    versions = {r.policy.validator_version for r in runs}
    if len(versions) > 1:
        raise ValueError("Mixed validator/protocol versions")
    for pid in POLICIES:
        if len({r.policy_hash for r in runs if r.policy.id == pid}) > 1:
            raise ValueError("Incompatible configurations for one policy")
    if provenance and "configs" in provenance and any(provenance["configs"].get(r.policy.id) != r.policy_hash for r in runs):
        raise ValueError("Configuration differs from assigned hash")
    if source == "benchmark" and versions == {"2"}:
        if not provenance or provenance.get("protocol_version") != "4" or provenance.get("validator_version") != "2":
            raise ValueError("Validator 2 benchmark requires protocol 4 provenance")
        if not provenance.get("reused_suite") or not provenance.get("evaluation_disclosure"):
            raise ValueError("Controlled rerun disclosure is required")
    elif provenance and provenance.get("protocol_version") == "4" and versions == {"1"}:
        raise ValueError("Legacy records cannot be labeled protocol 4")
    summaries = []
    for pid in POLICIES:
        group = [r for r in runs if r.policy.id == pid]
        assigned = assigned_per_policy if assigned_per_policy is not None else len(group)
        if len(group) > assigned:
            raise ValueError("More completed executions than assigned")
        summaries.append({"id": pid, **summarize(group, assigned)})
    by_id = {s["id"]: s for s in summaries}
    ultra = by_id["ultra_only"]
    acceptable = [
        s
        for s in summaries[:3]
        if s["success_rate"] >= 0.9
        and s["successes"] >= ultra["successes"]
        and len(s["incorrect_accepted_mutations"]) <= len(ultra["incorrect_accepted_mutations"])
        and s["critical_errors"] == 0
        and s["incomplete_measurements"] == 0
        and s["total_estimated_usd"] is not None
    ]
    cheapest = min(acceptable, key=lambda s: s["total_estimated_usd"]) if acceptable else None
    paired = []
    for s in summaries:
        cost, base = s["total_estimated_usd"], ultra["total_estimated_usd"]
        s["savings_vs_ultra"] = 1 - cost / base if cost is not None and base else None
        s["savings_vs_single"] = (
            1 - cost / cheapest["total_estimated_usd"]
            if cheapest and cost is not None and cheapest["total_estimated_usd"]
            else None
        )
        s["quality_delta_pp"] = 100 * (s["success_rate"] - ultra["success_rate"])
        s["qualifies"] = bool(
            source == "benchmark"
            and s["assigned"] > 0
            and not s["incomplete_measurements"]
            and not ultra["incomplete_measurements"]
            and s["success_rate"] >= 0.9
            and s["successes"] >= ultra["successes"]
            and (s["savings_vs_ultra"] or 0) >= 0.3
            and s["critical_errors"] == 0
            and len(s["incorrect_accepted_mutations"]) <= len(ultra["incorrect_accepted_mutations"])
        )
        for run in [r for r in runs if r.policy.id == s["id"]]:
            baseline = next(
                (
                    r
                    for r in runs
                    if r.policy.id == "ultra_only"
                    and r.task.id == run.task.id
                    and r.repetition == run.repetition
                ),
                None,
            )
            if baseline and run.outcome and baseline.outcome:
                paired.append(
                    {
                        "task_id": run.task.id,
                        "repetition": run.repetition,
                        "policy": s["id"],
                        "success": run.outcome.success,
                        "ultra_success": baseline.outcome.success,
                    }
                )
    if split == "development" and source == "benchmark":
        qualifying = [s for s in summaries if s["qualifies"]]
        selected = min(qualifying, key=lambda s: s["total_estimated_usd"])["id"] if qualifying else None
    status = (
        "test_fixture"
        if source == "test_fixture"
        else ("validated" if selected and by_id[selected]["qualifies"] else "not_validated")
    )
    return BenchmarkReport(
        id=digest({"runs": [r.id for r in runs], "manifest": manifest, "selected": selected})[:16],
        created_at=now(),
        source=source,
        split=split,
        manifest_hash=digest(manifest),
        provenance={
            **(provenance or {}),
            "completion_status": "complete" if len(runs) == sum(s["assigned"] for s in summaries) else "incomplete",
            "assignment_accounting": {
                "assigned": sum(s["assigned"] for s in summaries),
                "completed_records": len(runs),
                "missing_records": sum(s["assigned"] for s in summaries) - len(runs),
            },
            "paired": paired,
            "cheapest_acceptable_single": cheapest["id"] if cheapest else None,
            "limitations": "Small synthetic workload: 20 held-out tasks cover 7 distinct scenarios. Repeated templates, numeric variants, and repetitions are not independent real-world task types. No task requests a return exceeding the remaining quantity after a prior return. Charges are estimates.",
        },
        policies=summaries,
        runs=runs,
        recommendation={
            "selected": selected,
            "status": status,
            "selected_on": "development",
            "reason": "No model measurements were made."
            if source == "test_fixture"
            else "Preselected candidate assessed without choosing a replacement from held-out results.",
        },
    )


def write_report(report, target):
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    from .contracts import canonical

    Path(target).write_text(canonical(public_export(report.model_dump(mode="json"))) + "\n")


def read_runs(directory):
    return [RunRecord.model_validate_json(p.read_text()) for p in sorted(Path(directory).glob("*.json"))]
