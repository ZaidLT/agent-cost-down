"""Vercel's ASGI entrypoint. Initialization is performed separately by the CLI."""

from agent_cost_down.api import app

__all__ = ["app"]
