"""No-inference verification that an exported config controls the inventory adapter."""

import asyncio
import json
from pathlib import Path

from agent_cost_down.contracts import PolicyConfig, policy
from agent_cost_down.demo import ScriptedProvider, test_catalog, tool
from agent_cost_down.fixtures import load_task
from agent_cost_down.runner import run_policy


async def main():
    task, snapshot = load_task(Path("fixtures-v3"), "resolution-development-1")
    task = task.model_copy(
        update={"adapter": "inventory", "id": "inventory-reservation", "request": "Reserve two mugs."}
    )
    config = policy(test_catalog(), "small_only", adapter="inventory")
    path = Path("artifacts/inventory-policy.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(config.model_dump_json(indent=2))
    loaded = PolicyConfig.model_validate_json(path.read_text())
    result = await run_policy(
        task,
        snapshot,
        loaded,
        ScriptedProvider([tool("reserve_inventory", {"sku": "MUG", "quantity": 2})]),
        source="test_fixture",
    )
    before = next(x["available"] for x in snapshot["stock"] if x["sku"] == "MUG")
    after = next(x["available"] for x in result.after["stock"] if x["sku"] == "MUG")
    assert result.resolution == "reserved" and after == before - 2
    print(
        json.dumps(
            {
                "source": "test_fixture",
                "adapter": loaded.adapter,
                "export_loaded": True,
                "reserved": before - after,
                "inference_calls": 0,
            }
        )
    )


asyncio.run(main())
