"""Explicitly scripted unit-test demonstration. Never used for model benchmarking."""

from .contracts import ModelCatalog, ModelSpec, Usage, now, policy
from .runner import run_policy


class ScriptedProvider:
    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    async def complete(self, model, messages, tools, limits, usage):
        self.seen.append({"model": model.id, "messages": messages.copy()})
        usage.append(
            Usage(
                model=model.id,
                input_tokens=0,
                output_tokens=0,
                estimated_usd=0.0,
                duration_ms=0.0,
                status="test_fixture",
            )
        )
        item = self.script.pop(0)
        return item


def tool(name, arguments, raw=None):
    import json

    return {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "fixture-call",
                "type": "function",
                "function": {"name": name, "arguments": raw if raw is not None else json.dumps(arguments)},
            }
        ],
    }


def test_catalog():
    return ModelCatalog(
        verified_at=now(),
        price_source="test fixture, not provider pricing",
        rpm=60,
        tpm=1000000,
        models={
            r: ModelSpec(id="test-" + r, input_usd_per_million=0.0, output_usd_per_million=0.0)
            for r in ("small", "super", "ultra")
        },
    )


async def demonstration(task, snapshot, pid="small_ultra"):
    order = next(
        o for o in snapshot["orders"] if o["customer_id"] == task.customer_id and o["status"] == "open"
    )
    line = next(l for l in snapshot["lines"] if l["order_id"] == order["id"] and l["sku"] == "BLUE-M")
    valid = tool(
        "submit_draft",
        {
            "order_id": order["id"],
            "changes": [{"operation": "replace", "line_id": line["id"], "sku": "BLACK-M"}],
        },
    )
    script = (
        [tool("submit_draft", {}, raw='{"order_id":'), valid]
        if pid in {"small_retry", "small_ultra"}
        else [valid]
    )
    return await run_policy(
        task, snapshot, policy(test_catalog(), pid), ScriptedProvider(script), source="test_fixture"
    )
