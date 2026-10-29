from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .contracts import POLICIES, Contract, ModelCatalog, PolicyConfig, digest
from .fixtures import load_task, require_current_suite
from .ledger import Denied, Ledger
from .privacy import public_export
from .provider import DurableRateLimiter, TokenFactory, maximum_cost
from .runner import run_policy

DEMO_TASKS = [
    "resolution-development-1",
    "amendment-development-1",
    "returns-development-2",
    "analysis-development-1",
    "ambiguity-development-1",
]


class Submission(Contract):
    task_id: str
    policy_id: str


def hosted_database_url():
    # The integration injects a different DATABASE_URL for each preview branch.
    # Prefer that value on Vercel over a manually copied, potentially stale URL.
    if os.getenv("VERCEL") and os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    return os.getenv("ACD_DATABASE_URL") or os.environ["DATABASE_URL"]


def create_app(db=None, model_catalog=None, provider_factory=None, policies=None, queue_sender=None):
    live = os.getenv("ACD_LIVE_ENABLED", "false").lower() == "true"
    mode = os.getenv("ACD_EXECUTION_MODE", "local")
    if mode not in {"local", "queue"}:
        raise ValueError("Execution mode must be local or queue")
    if os.getenv("VERCEL") and live and mode != "queue":
        raise RuntimeError("Vercel live execution requires the private queue consumer")
    if live and os.getenv("VERCEL_ENV") == "preview":
        raise RuntimeError("Branched previews cannot spend inference credit; use the protected production ledger")
    root = Path(os.getenv("ACD_SUITE", "fixtures-v3"))
    if live:
        require_current_suite(root)
    state = {"worker": None, "db": db, "models": model_catalog, "policies": policies}

    async def worker(once=False):
        database = state["db"]
        while True:
            try:
                row = database.claim(str(uuid.uuid4()), hosted=True)
            except (Denied, SQLAlchemyError):
                if once:
                    raise
                return
            if not row:
                delay = database.active_lease_delay()
                if delay is not None:
                    if once:
                        raise RuntimeError("Another run retains the execution lease")
                    await asyncio.sleep(delay + 0.1)
                    continue
                return
            provider = None
            try:
                task, snapshot = load_task(root, row["task_id"])
                config = state["policies"][row["policy_id"]]
                expected_payload = digest(
                    {
                        "request": {"task_id": task.id, "policy_id": config.id},
                        "task_hash": digest(task),
                        "policy_hash": digest(config),
                    }
                )
                if expected_payload != row["payload_hash"]:
                    raise ValueError("Queued task or policy changed after admission")
                provider = (
                    provider_factory(database.hook(row["id"]))
                    if provider_factory
                    else TokenFactory(
                        state["models"].rpm,
                        state["models"].tpm,
                        hook=database.hook(row["id"]),
                        limiter=state["limiter"],
                    )
                )
                result = await run_policy(task, snapshot, config, provider, run_id=row["id"])
                from .evaluation.outcomes import evaluate_from_file

                result.outcome = evaluate_from_file(result, root)
                import time

                result.elapsed_queue_ms = max(0.0, (time.time() - row["created"]) * 1000 - result.duration_ms)
                database.finish(row["id"], public_export(result.model_dump(mode="json")))
            except BaseException:
                database.finish(
                    row["id"], error="Execution failed or was interrupted. No uncertain request is repeated."
                )
                if isinstance(__import__("sys").exception(), asyncio.CancelledError):
                    raise
            finally:
                if provider:
                    await provider.close()
            if once:
                return

    def wake():
        if live and mode == "local" and (state["worker"] is None or state["worker"].done()):
            state["worker"] = asyncio.create_task(worker())

    @asynccontextmanager
    async def lifespan(app):
        if live:
            if not os.getenv("ACD_CLIENT_SALT") or not os.getenv("ACD_JUDGE_CODE"):
                raise RuntimeError("Live mode requires private quota salt and judge code")
            state["db"] = state["db"] or Ledger(hosted_database_url())
            state["models"] = state["models"] or ModelCatalog.model_validate_json(
                os.getenv("ACD_MODELS_JSON")
                or Path(os.getenv("ACD_MODELS", "private/models.json")).read_text()
            )
            if state["policies"] is None:
                raw = json.loads(
                    os.getenv("ACD_POLICIES_JSON")
                    or Path(os.getenv("ACD_POLICIES", "private/policies.json")).read_text()
                )
                state["policies"] = {
                    k: PolicyConfig.model_validate_json(json.dumps(v)) for k, v in raw.items()
                }
            if set(state["policies"]) != set(POLICIES):
                raise RuntimeError("All five pinned policies are required")
            allowed = {digest(m) for m in state["models"].models.values()}
            if any(digest(m) not in allowed for p in state["policies"].values() for m in p.models):
                raise RuntimeError("Pinned policies differ from verified model catalog")
            if mode == "queue" and any(p.limits.deadline_seconds > 180 for p in state["policies"].values()):
                raise RuntimeError("Queue hosting requires the validated 180-second policy deadline")
            state["limiter"] = DurableRateLimiter(state["db"], state["models"].rpm, state["models"].tpm)
            if mode == "queue":
                state["db"].recover_queue()
            state["db"].purge_traces()
            wake()
        yield
        if state["worker"] and not state["worker"].done():
            state["worker"].cancel()
            try:
                await state["worker"]
            except asyncio.CancelledError:
                pass

    app = FastAPI(title="Agent Cost Down", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.run_one = lambda: worker(once=True)
    preparation = os.getenv("ACD_PREPARATION_MODE", "false").lower() == "true"
    preparation_token = os.getenv("ACD_PREPARATION_TOKEN", "")
    if preparation and not preparation_token:
        raise RuntimeError("Preparation mode requires a private access token")

    @app.middleware("http")
    async def preparation_access(request, call_next):
        if preparation and not hmac.compare_digest(
            request.headers.get("authorization", "").encode(), ("Bearer " + preparation_token).encode()
        ):
            return JSONResponse({"detail": "Private preparation deployment"}, status_code=401)
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("ACD_ALLOWED_ORIGINS", "http://localhost:5173").split(","),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-Judge-Code", "Authorization"],
    )

    if preparation:
        @app.get("/v1/preparation/network", include_in_schema=False)
        async def network_check(request: Request):
            # Protected by the preparation bearer token; never enabled in the public release.
            return {"peer": request.client.host if request.client else None,
                    "forwarded": request.headers.getlist("x-forwarded-for"),
                    "cloudflare_client": request.headers.get("cf-connecting-ip")}

    @app.get("/healthz")
    async def health():
        return {"status": "ok", "live_enabled": live}

    @app.get("/v1/catalog")
    async def catalog():
        available = False
        if live:
            try:
                available = state["db"].remaining("public") > 0 or state["db"].remaining("judge") > 0
            except (Denied, SQLAlchemyError):
                available = False
        return {
            "tasks": DEMO_TASKS,
            "policies": list(POLICIES),
            "schema_version": 1,
            "policy_hashes": {k: digest(v) for k, v in (state["policies"] or {}).items()},
            "configurations": {k: v.model_dump(mode="json") for k, v in (state["policies"] or {}).items()},
            "available": available,
            "message": "Live runs require confirmed credit reservations.",
        }

    @app.post("/v1/runs", status_code=202)
    async def submit(
        body: Submission,
        request: Request,
        idempotency_key: str = Header(),
        x_judge_code: str | None = Header(default=None),
    ):
        if not live or not state["db"]:
            raise HTTPException(503, "Live execution is disabled. Recorded reports remain available.")
        if not 8 <= len(idempotency_key) <= 128:
            raise HTTPException(400, "Use an idempotency key of 8 to 128 characters")
        if body.task_id not in DEMO_TASKS or body.policy_id not in POLICIES:
            raise HTTPException(400, "Choose an allowlisted demo task and policy")
        judge = bool(x_judge_code and hmac.compare_digest(x_judge_code, os.environ["ACD_JUDGE_CODE"]))
        if x_judge_code and not judge:
            raise HTTPException(403, "Judge code is invalid")
        # Uvicorn trusts only the deployment proxy configured by FORWARDED_ALLOW_IPS.
        address = request.client.host if request.client else "unknown"
        if os.getenv("VERCEL"):
            # Vercel overwrites this header at its trusted ingress. Do not trust generic X-Forwarded-For.
            address = request.headers.get("x-vercel-forwarded-for", "").strip()
            if not address or "," in address:
                raise HTTPException(503, "Trusted client address unavailable")
        elif os.getenv("RENDER") == "true":
            # Enable only after a protected spoof-header probe verifies Render's Cloudflare ingress.
            if os.getenv("ACD_RENDER_PROXY_VERIFIED") != "true":
                raise HTTPException(503, "Trusted client address has not been verified")
            try:
                address = str(ipaddress.ip_address(request.headers.get("cf-connecting-ip", "")))
            except ValueError:
                raise HTTPException(503, "Trusted client address unavailable") from None
        client = hmac.new(
            os.environ["ACD_CLIENT_SALT"].encode(), address.encode(), hashlib.sha256
        ).hexdigest()
        config = state["policies"][body.policy_id]
        try:
            task, _ = load_task(root, body.task_id)
            state["db"].purge_traces()
            if mode == "queue":
                state["db"].recover_queue()
            row = state["db"].submit(
                task_id=body.task_id,
                policy_id=body.policy_id,
                client=client,
                key=idempotency_key,
                pool="judge" if judge else "public",
                reserve=maximum_cost(config),
                payload_hash=digest(
                    {"request": body.model_dump(), "task_hash": digest(task), "policy_hash": digest(config)}
                ),
            )
        except Denied as exc:
            raise HTTPException(429, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(503, "Spending ledger unavailable; no call was dispatched") from exc
        if mode == "queue":
            try:
                if state["db"].begin_dispatch(row["id"]):
                    if queue_sender:
                        await queue_sender(row["id"])
                    else:
                        from vercel.queue import send

                        await send(
                            "acd-live-runs", {"run_id": row["id"]}, idempotency_key=row["id"], retention=900
                        )
                    state["db"].sent_dispatch(row["id"])
                row = state["db"].get(row["id"])
            except Exception as exc:
                try:
                    state["db"].fail_dispatch(row["id"])
                except SQLAlchemyError:
                    logging.getLogger(__name__).warning("Queue recovery pending: ledger unavailable")
                raise HTTPException(
                    503, "Queue dispatch uncertain; check this request using the same idempotency key"
                ) from exc
        else:
            wake()
        return {"id": row["id"], "status": row["status"]}

    @app.get("/v1/runs/{run_id}")
    async def read_run(run_id: uuid.UUID):
        if not live or not state["db"]:
            raise HTTPException(503, "Live execution disabled")
        try:
            if mode == "queue":
                state["db"].recover_queue()
            row = state["db"].get(str(run_id))
        except Exception as exc:
            raise HTTPException(503, "Job store unavailable") from exc
        if not row:
            raise HTTPException(404, "Run not found")
        return {k: row[k] for k in ("id", "status", "result", "error")}

    return app


app = create_app()
