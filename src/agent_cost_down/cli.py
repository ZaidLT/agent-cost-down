from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import sys
from pathlib import Path

from .contracts import (
    POLICIES,
    BenchmarkReport,
    Limits,
    ModelCatalog,
    PolicyConfig,
    PublicTask,
    RunRecord,
    canonical,
    digest,
    policy,
)
from .fixtures import generate, load_task, suite_tasks
from .ledger import Credits, Denied, Ledger
from .privacy import public_export
from .provider import RateLimiter, TokenFactory, maximum_cost
from .runner import run_policy


def read_model(path, cls):
    return cls.model_validate_json(Path(path).read_text())


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(public_export(value), indent=2) + "\n")


def ledger():
    return Ledger(os.getenv("ACD_DATABASE_URL", "sqlite:///private/operations.db"))


def catalog(args):
    return read_model(args.models, ModelCatalog)


async def execute(
    task,
    snapshot,
    config,
    models,
    output,
    *,
    pool,
    key,
    repetition=0,
    source="live",
    limiter=None,
    max_active=1,
):
    from .evaluation.outcomes import evaluate_from_file

    allowed = {digest(m) for m in models.models.values()}
    if any(digest(m) not in allowed for m in config.models):
        raise ValueError("Policy contains models or prices not present in the verified account catalog")
    if not os.getenv("NEBIUS_API_KEY"):
        raise ValueError("Set NEBIUS_API_KEY locally before reserving or starting an inference run")
    db = ledger()
    row = db.submit(
        task_id=task.id,
        policy_id=config.id,
        client="local",
        key=key,
        pool=pool,
        reserve=maximum_cost(config),
        payload_hash=digest({"task": task, "config": config}),
        hosted=False,
    )
    if row["status"] != "queued":
        if row["result"]:
            save(output, row["result"])
            return RunRecord.model_validate_json(json.dumps(row["result"]))
        raise Denied("Existing execution is interrupted or incomplete; it will not be silently repeated")
    if not db.claim("local-cli", config.limits.deadline_seconds + 60, row["id"], max_active=max_active):
        raise Denied("Another run holds the execution lease")
    provider = TokenFactory(models.rpm, models.tpm, hook=db.hook(row["id"]), limiter=limiter)
    try:
        record = await run_policy(
            task, snapshot, config, provider, repetition=repetition, source=source, run_id=row["id"]
        )
        record.outcome = evaluate_from_file(record, Path(os.getenv("ACD_SUITE", "fixtures")))
        clean = public_export(record.model_dump(mode="json"))
        db.finish(row["id"], clean)
        save(output, clean)
        return record
    except BaseException:
        db.finish(row["id"], error="Execution interrupted or failed; inspect the durable ledger")
        raise
    finally:
        await provider.close()


async def main_async(args):
    root = Path(args.suite)
    os.environ["ACD_SUITE"] = str(root)
    if args.command == "generate":
        manifest = generate(
            root, args.seed, quantity_base=args.quantity_base, return_days=args.return_days, as_of=args.as_of
        )
        print(f"Generated {len(manifest['tasks'])} tasks. Human review is pending.")
    elif args.command == "doctor":
        info = {
            "python": sys.version.split()[0],
            "provider_key_present": bool(os.getenv("NEBIUS_API_KEY")),
            "models_configured": Path(args.models).exists(),
            "credits_configured": Path(args.credits).exists(),
            "fixtures_present": (root / "manifest.json").exists(),
            "cash_budget_usd": 0,
        }
        if args.initialize_ledger:
            database = ledger()
            database.initialize_schema()
            database.configure(read_model(args.credits, Credits))
            info["ledger_initialized"] = True
        if args.online:
            import httpx

            async with httpx.AsyncClient() as client:
                result = await client.get(
                    "https://api.tokenfactory.nebius.com/v1/models",
                    headers={"Authorization": "Bearer " + os.environ["NEBIUS_API_KEY"]},
                )
                result.raise_for_status()
                info["available_model_ids"] = [m["id"] for m in result.json().get("data", [])]
        if args.schemas:
            from .contracts import AttemptResult, FailureContext

            for cls in (PublicTask, AttemptResult, PolicyConfig, RunRecord, BenchmarkReport, FailureContext):
                save(Path(args.schemas) / (cls.__name__ + ".json"), cls.model_json_schema())
        print(json.dumps(info, indent=2))
    elif args.command == "smoke" and args.offline:
        from .demo import demonstration
        from .evaluation.outcomes import evaluate_from_file
        from .reporting import build_report, write_report

        task, snapshot = load_task(root, "resolution-development-1")
        runs = []
        for pid in POLICIES:
            record = await demonstration(task, snapshot, pid)
            record.outcome = evaluate_from_file(record, root)
            runs.append(record)
        manifest = json.loads((root / "manifest.json").read_text())
        report = build_report(
            runs,
            manifest,
            "development",
            "test_fixture",
            assigned_per_policy=1,
            provenance={"method": "Scripted unit-test illustration. No model calls."},
        )
        write_report(report, args.output)
        print(f"Saved explicitly labeled test fixture to {args.output}. No inference or savings measured.")
    elif args.command in {"smoke", "run"}:
        models = catalog(args)
        task, snapshot = load_task(root, args.task)
        config = (
            read_model(args.config, PolicyConfig)
            if getattr(args, "config", None)
            else policy(models, args.policy)
        )
        result = await execute(
            task,
            snapshot,
            config,
            models,
            args.output,
            pool="development",
            key=args.key or str(__import__("uuid").uuid4()),
        )
        print(
            json.dumps(
                {
                    "run": result.id,
                    "verdict": result.verdict,
                    "outcome": result.outcome.model_dump(),
                    "estimated_usd": result.total_estimated_usd,
                },
                indent=2,
            )
        )
    elif args.command == "benchmark":
        from .protocol import code_hash, freeze, verify_freeze

        models = catalog(args)
        if args.freeze_from:
            frozen = freeze(
                root, models, Limits(deadline_seconds=args.deadline), args.freeze_from, args.freeze
            )
            print(json.dumps({"frozen": args.freeze, "selected": frozen["selected"]}, indent=2))
            return
        frozen = json.loads(Path(args.freeze).read_text()) if args.split == "heldout" else None
        manifest = verify_freeze(root, frozen) if frozen else json.loads((root / "manifest.json").read_text())
        if frozen and digest(models) != digest(frozen["catalog"]):
            raise ValueError("Account model catalog differs from frozen catalog")
        configs = {
            p: PolicyConfig.model_validate_json(json.dumps(frozen["policies"][p]))
            if frozen
            else policy(models, p, Limits(deadline_seconds=args.deadline))
            for p in POLICIES
        }
        ids = suite_tasks(root, args.split)
        repetitions = 3 if frozen else 1
        schedule = [(tid, rep, pid) for rep in range(repetitions) for tid in ids for pid in POLICIES]
        random.Random(20261026).shuffle(schedule)
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        pilot_hash = None
        if args.concurrency == 2:
            from .batch import validate_parallel_pilot

            pilot_hash = validate_parallel_pilot(
                args.pilot_evidence, models, next(iter(configs.values())).limits
            )
        if frozen and (args.concurrency != frozen["concurrency"] or pilot_hash != frozen["pilot_hash"]):
            raise ValueError("Concurrency or pilot evidence differs from the development freeze")
        assignment = {
            "concurrency": args.concurrency,
            "pilot_hash": pilot_hash,
            "split": args.split,
            "schedule": schedule,
            "code_hash": code_hash(),
            "manifest_hash": digest(manifest),
            "configs": {p: digest(c) for p, c in configs.items()},
            "freeze_hash": digest(frozen),
            "selected": frozen["selected"] if frozen else None,
        }
        assignment_path = output / "assignment.json"
        if assignment_path.exists() and json.loads(assignment_path.read_text()) != json.loads(
            canonical(assignment)
        ):
            raise ValueError("Existing batch assignment differs")
        save(assignment_path, assignment)
        forecast = sum(maximum_cost(configs[pid]) for _, _, pid in schedule)
        print(
            json.dumps(
                {
                    "assigned": len(schedule),
                    "worst_case_reservation_usd": forecast,
                    "execution": args.execute,
                    "deadline_seconds": next(iter(configs.values())).limits.deadline_seconds,
                }
            )
        )
        if not args.execute:
            return
        # Forecast the batch; reserve the maximum for each run only when it is about to start.
        db = ledger()
        from datetime import UTC, datetime, timedelta

        credits = read_model(args.credits, Credits)
        credit_age = (datetime.now(UTC) - datetime.fromisoformat(credits.confirmed_at)).total_seconds()
        if not 0 <= credit_age <= 86400:
            raise Denied("Recheck actual credits and refresh the evidence file before a large batch")
        if frozen:
            remaining_fraction = sum(
                not (output / "runs" / f"{tid}-{rep}-{pid}.json").exists() for tid, rep, pid in schedule
            ) / len(schedule)
            if frozen["forecast_usd"] * remaining_fraction + max(
                maximum_cost(c) for c in configs.values()
            ) > db.remaining("evaluation"):
                raise Denied("Measured forecast plus 50% headroom exceeds the evaluation allocation")
            if args.completion_deadline:
                finish_by = datetime.fromisoformat(args.completion_deadline)
                if finish_by.tzinfo is None:
                    raise ValueError("Completion deadline requires a timezone")
                if (
                    datetime.now(UTC) + timedelta(seconds=frozen["forecast_seconds"] * remaining_fraction)
                    > finish_by
                ):
                    raise Denied("Measured forecast misses the requested completion window")
        shared_limiter = RateLimiter(models.rpm, models.tpm)

        async def run_assignment(item):
            tid, rep, pid = item
            task, snapshot = load_task(root, tid)
            key = digest({"assignment": assignment, "task": tid, "repetition": rep, "policy": pid})
            row = db.submit(
                task_id=tid,
                policy_id=pid,
                client="local",
                key=key,
                pool="evaluation" if frozen else "development",
                reserve=maximum_cost(configs[pid]),
                hosted=False,
                payload_hash=digest({"task": task, "config": configs[pid]}),
            )
            if frozen:
                verify_freeze(root, frozen)
            path = output / "runs" / f"{task.id}-{rep}-{pid}.json"
            if path.exists():
                saved = read_model(path, RunRecord)
                if saved.id != row["id"] or saved.policy_hash != digest(configs[pid]):
                    raise ValueError("Checkpoint provenance mismatch")
                return
            if row["status"] not in {"queued", "complete"}:
                print(f"Preserving incomplete assigned run {row['id']}; it remains in the denominator.")
                return
            try:
                await execute(
                    task,
                    snapshot,
                    configs[pid],
                    models,
                    path,
                    pool="evaluation" if frozen else "development",
                    key=key,
                    repetition=rep,
                    source="benchmark",
                    limiter=shared_limiter,
                    max_active=args.concurrency,
                )
            except Denied:
                raise
            except Exception as exc:  # noqa: BLE001 - preserve the assigned denominator without publishing raw errors
                logging.getLogger(__name__).error(
                    "Execution failed (%s); see the sanitized ledger", type(exc).__name__
                )
                print(f"Run failed: {row['id']}. Failure preserved in the ledger.")

        from .batch import run_bounded

        await run_bounded(schedule, run_assignment, args.concurrency)
    elif args.command == "report":
        from .reporting import build_report, read_runs, write_report

        assignment = json.loads((Path(args.input) / "assignment.json").read_text())
        runs = read_runs(Path(args.input) / "runs")
        manifest = json.loads((root / "manifest.json").read_text())
        if assignment["manifest_hash"] != digest(manifest):
            raise ValueError("Report manifest mismatch")
        report = build_report(
            runs,
            manifest,
            assignment["split"],
            "benchmark",
            selected=assignment["selected"],
            assigned_per_policy=len(assignment["schedule"]) // 5,
            provenance=assignment,
        )
        write_report(report, args.output)
        print(f"Saved {report.recommendation['status']} report to {args.output}")
    elif args.command == "export-policy":
        report = read_model(args.report, BenchmarkReport)
        pid = args.policy or report.recommendation["selected"]
        candidate = next((r.policy for r in report.runs if r.policy.id == pid), None)
        if candidate is None:
            raise ValueError("Choose a policy that exists in this report")
        candidate = candidate.model_copy(update={"supporting_report": report.id})
        save(args.output, candidate.model_dump(mode="json"))
        print(
            f"Exported runnable configuration to {args.output}; report status is {report.recommendation['status']}"
        )
    elif args.command == "serve":
        import uvicorn

        server = uvicorn.Server(
            uvicorn.Config("agent_cost_down.api:app", host=args.host, port=args.port, workers=1)
        )
        await server.serve()


def main():
    parser = argparse.ArgumentParser(
        description="Reproducible policy execution with independent outcome evaluation"
    )
    parser.add_argument("--suite", default=os.getenv("ACD_SUITE", "fixtures"))
    parser.add_argument("--models", default=os.getenv("ACD_MODELS", "private/models.json"))
    parser.add_argument("--credits", default=os.getenv("ACD_CREDITS", "private/credits.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("generate")
    p.add_argument("--seed", type=int, default=20261024)
    p.add_argument("--quantity-base", type=int, default=3)
    p.add_argument("--return-days", type=int, default=30)
    p.add_argument("--as-of", default="2026-10-24")
    p = sub.add_parser("doctor")
    p.add_argument("--online", action="store_true")
    p.add_argument("--initialize-ledger", action="store_true")
    p.add_argument("--schemas")
    for command in ("smoke", "run"):
        p = sub.add_parser(command)
        p.add_argument("--task", default="resolution-development-1")
        p.add_argument("--policy", choices=list(POLICIES), default="small_ultra")
        p.add_argument("--output", default="artifacts/smoke.json")
        p.add_argument("--key")
        if command == "smoke":
            p.add_argument("--offline", action="store_true")
        else:
            p.add_argument("--config", required=True)
    p = sub.add_parser("benchmark")
    p.add_argument("--split", choices=["development", "heldout"], default="development")
    p.add_argument("--deadline", type=int, choices=[180, 300, 600], default=180)
    p.add_argument(
        "--completion-deadline",
        default="2026-10-30T12:00:00+03:00",
        help="ISO timestamp for the batch scheduling gate",
    )
    p.add_argument("--concurrency", type=int, choices=[1, 2], default=1)
    p.add_argument("--pilot-evidence")
    p.add_argument("--freeze", default="artifacts/freeze.json")
    p.add_argument("--freeze-from")
    p.add_argument("--output", default="artifacts/batch")
    p.add_argument("--execute", action="store_true")
    p = sub.add_parser("report")
    p.add_argument("--input", default="artifacts/batch")
    p.add_argument("--output", default="artifacts/report.json")
    p = sub.add_parser("export-policy")
    p.add_argument("--report", required=True)
    p.add_argument("--policy", choices=list(POLICIES))
    p.add_argument("--output", default="artifacts/policy.json")
    p = sub.add_parser("serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        asyncio.run(main_async(args))
    except (ValueError, OSError, KeyError) as exc:
        print(
            f"Stopped: {type(exc).__name__}. {str(exc) if not isinstance(exc, OSError) else 'Check local files and account setup.'}",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
