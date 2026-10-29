"""Bounded scheduling with admission stopped after a fatal batch error."""

import asyncio
import json
from pathlib import Path

from .contracts import digest
from .protocol import code_hash


def validate_parallel_pilot(path, models, limits):
    if not path:
        raise ValueError("Concurrency two requires verified parallel pilot evidence")
    evidence = json.loads(Path(path).read_text())
    if (
        evidence.get("source") != "live"
        or evidence.get("development_only") is not True
        or evidence.get("concurrency") != 2
        or evidence.get("runs") != 18
        or evidence.get("model_catalog_hash") != digest(models)
        or evidence.get("code_hash") != code_hash()
        or evidence.get("deadline_seconds") != limits.deadline_seconds
        or set(evidence.get("models", {})) != {"small_only", "super_only", "ultra_only"}
    ):
        raise ValueError("Parallel pilot does not match this frozen execution setup")
    for group in evidence["models"].values():
        if group.get("runs") != 6 or any(
            group.get(field, 1) != 0
            for field in ("rate_limited_calls", "interrupted_calls", "incomplete_measurements")
        ):
            raise ValueError("Parallel pilot contains throttling or incomplete measurements")
    return digest(evidence)


async def run_bounded(schedule, execute, concurrency):
    if concurrency not in {1, 2}:
        raise ValueError("Batch concurrency must be one or two")
    remaining = iter(schedule)
    errors = []

    async def worker():
        while not errors:
            item = next(remaining, None)
            if item is None:
                return
            try:
                await execute(item)
            except Exception as exc:  # noqa: BLE001 - settle admitted work before propagating
                errors.append(exc)

    # Let already-admitted work settle. Do not abandon accounting on a fatal error.
    await asyncio.gather(*(worker() for _ in range(concurrency)))
    if errors:
        raise errors[0]
