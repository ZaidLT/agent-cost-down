"""Private Vercel subscriber. No HTTP callback or public execution endpoint."""

import os

from vercel.queue import Message, subscribe

from agent_cost_down.api import create_app


@subscribe(topic="acd-live-runs", max_concurrency=1, retry_after=10, max_attempts=90)
async def consume(message: Message[dict[str, str]]) -> None:
    if os.getenv("ACD_LIVE_ENABLED", "false").lower() != "true":
        return
    if os.getenv("ACD_EXECUTION_MODE") != "queue":
        raise RuntimeError("Private consumer requires queue execution mode")
    # Messages are wake-ups. The transactional ledger picks the highest-priority
    # queued job and prevents duplicate execution across deliveries/deployments.
    app = create_app()
    async with app.router.lifespan_context(app):
        await app.state.run_one()
