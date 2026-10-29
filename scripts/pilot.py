"""Bounded development-only latency/throughput pilot. Dry run unless --execute is supplied."""

import argparse
import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from agent_cost_down.cli import execute, read_model, save
from agent_cost_down.contracts import Limits, ModelCatalog, digest, policy
from agent_cost_down.fixtures import load_task
from agent_cost_down.ledger import Credits
from agent_cost_down.protocol import code_hash
from agent_cost_down.provider import RateLimiter, maximum_cost
from agent_cost_down.reporting import percentile

TASKS = [
    "resolution-development-1",
    "amendment-development-1",
    "returns-development-1",
    "returns-development-2",
    "analysis-development-1",
    "ambiguity-development-1",
]


async def main(args):
    models = read_model(args.models, ModelCatalog)
    root, destination = Path(args.suite), Path(args.output)
    os.environ["ACD_SUITE"] = str(root)
    configs = {
        pid: policy(models, pid, Limits(deadline_seconds=args.deadline))
        for pid in ("small_only", "super_only", "ultra_only")
    }
    schedule = [(task, pid) for task in TASKS for pid in configs]
    print(
        json.dumps(
            {
                "assigned": len(schedule),
                "concurrency": args.concurrency,
                "deadline_seconds": args.deadline,
                "sum_of_per_run_maxima_usd": sum(maximum_cost(configs[p]) for _, p in schedule),
                "execute": args.execute,
            }
        )
    )
    if not args.execute:
        return
    credits = read_model(args.credits, Credits)
    age = (datetime.now(UTC) - datetime.fromisoformat(credits.confirmed_at)).total_seconds()
    if not 0 <= age <= 86400:
        raise ValueError("Recheck actual credits and update the evidence file before the pilot")
    semaphore = asyncio.Semaphore(args.concurrency)
    limiter = RateLimiter(models.rpm, models.tpm)
    started = time.monotonic()
    records = []

    async def one(task_id, pid):
        async with semaphore:
            task, snapshot = load_task(root, task_id)
            config = configs[pid]
            key = digest(
                {
                    "pilot": str(destination),
                    "concurrency": args.concurrency,
                    "task": task.id,
                    "config": config,
                }
            )
            record = await execute(
                task,
                snapshot,
                config,
                models,
                destination / "runs" / (task_id + "-" + pid + ".json"),
                pool="development",
                key=key,
                limiter=limiter,
                max_active=args.concurrency,
            )
            records.append(record)

    await asyncio.gather(*(one(t, p) for t, p in schedule))
    elapsed = time.monotonic() - started
    summary = {
        "source": "live",
        "code_hash": code_hash(),
        "records_hash": digest([r.model_dump(mode="json") for r in records]),
        "development_only": True,
        "concurrency": args.concurrency,
        "deadline_seconds": args.deadline,
        "runs": len(records),
        "wall_seconds": elapsed,
        "runs_per_minute": len(records) * 60 / elapsed,
        "model_catalog_hash": digest(models),
        "models": {},
    }
    for pid in configs:
        group = [r for r in records if r.policy.id == pid]
        usage = [u for r in group for a in r.attempts for u in a.usage]
        summary["models"][pid] = {
            "runs": len(group),
            "model_calls": len(usage),
            "p95_seconds": percentile([r.duration_ms / 1000 for r in group], 0.95),
            "input_tokens": sum(u.input_tokens or 0 for u in usage),
            "output_tokens": sum(u.output_tokens or 0 for u in usage),
            "rate_limited_calls": sum(u.status == "rate_limited" for u in usage),
            "interrupted_calls": sum(u.status == "interrupted" for u in usage),
            "incomplete_measurements": sum(not r.measurement_complete for r in group),
            "estimated_usd": sum(r.total_estimated_usd for r in group)
            if all(r.measurement_complete for r in group)
            else None,
        }
    save(destination / "pilot.json", summary)
    print(json.dumps(summary, indent=2))


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--models", default="private/models.json")
parser.add_argument("--credits", default="private/credits.json")
parser.add_argument("--suite", default="fixtures")
parser.add_argument("--output", required=True)
parser.add_argument("--concurrency", type=int, choices=[1, 2], default=1)
parser.add_argument("--deadline", type=int, choices=[180, 300, 600], default=180)
parser.add_argument("--execute", action="store_true")
if __name__ == "__main__":
    asyncio.run(main(parser.parse_args()))
