"""Offline v3 diagnostic replay. Never overwrites benchmark records or invokes inference."""
import json
from collections import Counter
from pathlib import Path

from agent_cost_down.contracts import RunRecord
from agent_cost_down.domain import World
from agent_cost_down.evaluation.outcomes import evaluate_from_file

results = {}
for split, expected_attempts, expected_finals in [("development", 12, 9), ("heldout", 48, 33)]:
    records = json.loads(Path(f"artifacts/{split}-v3-300-report.json").read_text())["runs"]
    counts = Counter()
    for raw in records:
        for index, attempt in enumerate(raw["attempts"]):
            context = attempt.get("failure_context")
            if not context or context["reason"] != "runtime_validation_failed":
                continue
            event = attempt["events"][-1]
            args = event.get("arguments", {})
            if event.get("tool") != "submit_draft" or not any(
                c.get("sku") is not None and c.get("quantity") is not None for c in args.get("changes", [])
            ):
                continue
            run = RunRecord.model_validate(raw)
            world = World(run.task, run.before)
            try:
                verdict, resolution, result = world.finish("submit_draft", world.types()["submit_draft"].model_validate(args))
                run.verdict, run.resolution, run.after = verdict, resolution, world.state()
                run.attempts = run.attempts[:index + 1]
                run.attempts[-1].result = result
                assert evaluate_from_file(run, Path("fixtures-v3")).success, raw["id"]
                counts["accepted_and_correct_attempts"] += 1
                if index == len(raw["attempts"]) - 1 and not raw["outcome"]["success"]:
                    counts["corrected_final_failures"] += 1
                    counts[raw["policy"]["id"]] += 1
            finally:
                world.close()
    assert counts["accepted_and_correct_attempts"] == expected_attempts, counts
    assert counts["corrected_final_failures"] == expected_finals, counts
    results[split] = dict(counts)
print(json.dumps({"source": "offline_counterfactual_replay", "model_calls": 0, "results": results}, indent=2))
